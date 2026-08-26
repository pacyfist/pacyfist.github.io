---
# SEO Target Queries:
#   Google: "c# new lock object", "c# 13 lock", "system.threading.lock", "c# params readonlyspan"
#   Bing:   "c# new lock object", "c# 13 params collections", "c# lock vs monitor"
tags: ["csharp", "dotnet", "concurrency", "performance", "csharp13"]
categories: ["csharp", "dotnet"]
title: "C# 13 Lock Object: One Cast Undoes the Whole Thing"
image:
  path: /assets/img/2026-08-24/main.jpg
  alt: Two doors into the same room, and only one of them has a lock that works.
published: false
---

I like the new `System.Threading.Lock`. I also like benchmarks, and the first benchmark I ran while writing this post told me the new lock is not faster than the `private readonly object _lock = new();` it replaces. Not a little faster. Not faster at all.

So I stopped writing the post I planned and built a lab instead: a console project, a disassembler, and a stopwatch. Every number, warning, and IL listing below came out of that lab. One of the results is a genuine footgun that I have not seen mentioned anywhere, and it silently turns your lock into no lock at all.

## The lab

Everything runs on the stable SDK, nothing preview:

```bash
dotnet --version
```

```text
10.0.111
```

The project pins the language version so the C# 13 features are unambiguous:

```xml
<TargetFramework>net10.0</TargetFramework>
<LangVersion>13</LangVersion>
```

A first sanity check, printing what we are actually sitting on:

```csharp
Console.WriteLine($"runtime : {System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription}");
```

```text
runtime : .NET 10.0.11
```

## What the compiler really emits

The claim everyone repeats is that `lock (someLock)` no longer compiles to `Monitor.Enter`. That is easy to check rather than believe. Here are two methods that look identical apart from the type of the field:

```csharp
public class Lowering
{
    private readonly object _oldGate = new();
    private readonly Lock _newGate = new();
    private int _counter;

    public void OldStyle()
    {
        lock (_oldGate) { _counter++; }
    }

    public void NewStyle()
    {
        lock (_newGate) { _counter++; }
    }
}
```

Build it and disassemble:

```bash
dotnet build -c Release
ilspycmd -il bin/Release/net10.0/illab.dll
```

`OldStyle` is the shape we have all known for twenty years, a `Monitor.Enter` with a bool flag and a `finally` that calls `Monitor.Exit`:

```text
IL_0009: ldloc.0
IL_000a: ldloca.s 1
IL_000c: call void [System.Threading]System.Threading.Monitor::Enter(object, bool&)
...
finally
{
  IL_0021: ldloc.1
  IL_0022: brfalse.s IL_002a
  IL_0024: ldloc.0
  IL_0025: call void [System.Threading]System.Threading.Monitor::Exit(object)
  IL_002a: endfinally
}
```

`NewStyle` is a different animal entirely:

```text
IL_0006: callvirt instance valuetype [System.Runtime]System.Threading.Lock/Scope
         [System.Runtime]System.Threading.Lock::EnterScope()
IL_000b: stloc.0
.try
{
  ...
}
finally
{
  IL_001c: ldloca.s 0
  IL_001e: call instance void [System.Runtime]System.Threading.Lock/Scope::Dispose()
  IL_0023: endfinally
}
```

Two things worth noticing. The `Dispose` is a plain `call`, not a `callvirt`, so there is no interface dispatch. And the whole method is smaller: the header comments in the listing read `Code size: 44 (0x2c)` for `OldStyle` and `Code size: 37 (0x25)` for `NewStyle`, with one local instead of two.

That `Scope` really is a `ref struct`, and it really does not implement `IDisposable`:

```csharp
var scopeType = typeof(Lock.Scope);
Console.WriteLine($"  IsValueType  : {scopeType.IsValueType}");
Console.WriteLine($"  IsByRefLike  : {scopeType.IsByRefLike}");
Console.WriteLine($"  implements IDisposable : {typeof(IDisposable).IsAssignableFrom(scopeType)}");
```

```text
[scope-type]
  full name    : System.Threading.Lock+Scope
  IsValueType  : True
  IsByRefLike  : True
  implements IDisposable : False
```

The `using` block works through pattern-based disposal instead of the interface. That is why there is no boxing and no virtual call.

## The trap: one cast and your lock stops locking

Here is the part that made me rewrite this post.

The compiler only emits `EnterScope()` when the **static type** at the `lock` keyword is `Lock`. Assign that same object to an `object` variable, and `lock` falls straight back to `Monitor`. Both lines look correct. They lock two completely different things.

```csharp
var real = new Lock();
object asObject = real;

lock (real)
{
    Console.WriteLine($"  lock(Lock)   -> IsHeldByCurrentThread : {real.IsHeldByCurrentThread}");
}
lock (asObject)
{
    Console.WriteLine($"  lock(object) -> IsHeldByCurrentThread : {real.IsHeldByCurrentThread}");
}
```

```text
[static-type-matters]
  lock(Lock)   -> IsHeldByCurrentThread : True
  lock(object) -> IsHeldByCurrentThread : False
```

Inside the second block we are holding *a* lock. We are just not holding **that** lock.

If that looks academic, here are two threads hammering the same gate. One thread locks it as a `Lock`, the other locks the very same instance as an `object`. If they are mutually exclusive, the counter never sees a second thread inside:

```csharp
var gate = new Lock();
object gateAsObject = gate;
int overlaps = 0;
int inside = 0;

var t1 = new Thread(() =>
{
    for (int i = 0; i < 200_000; i++)
        lock (gate) { if (Interlocked.Increment(ref inside) != 1) Interlocked.Increment(ref overlaps); Interlocked.Decrement(ref inside); }
});
var t2 = new Thread(() =>
{
    for (int i = 0; i < 200_000; i++)
        lock (gateAsObject) { if (Interlocked.Increment(ref inside) != 1) Interlocked.Increment(ref overlaps); Interlocked.Decrement(ref inside); }
});
t1.Start(); t2.Start(); t1.Join(); t2.Join();
Console.WriteLine($"  overlapping critical sections observed : {overlaps}");
```

```text
[mutual-exclusion-across-static-types]
  overlapping critical sections observed : 44287
```

Forty-four thousand times, both threads were inside the critical section at once. The lock was doing nothing.

The good news is that the compiler does see this coming, and I got the warning three times in my lab build without asking for it:

```text
warning CS9216: A value of type 'System.Threading.Lock' converted to a different type will use
likely unintended monitor-based locking in 'lock' statement.
```

**Treat CS9216 as an error.** It is the only thing standing between you and a lock that silently does not lock. Any place a `Lock` gets stored in an `object` field, passed to a helper that takes `object`, or captured by an older API, you lose the guarantee and keep the syntax.

The same split shows up in the `Monitor` API. Call `Monitor.Pulse` on the object-typed reference and it works, because that is a plain monitor. Call it on the `Lock`, and it throws:

```csharp
try { lock (asObject) { Monitor.Pulse(asObject); Console.WriteLine("  Monitor.Pulse(lockAsObject) : ok"); } }
catch (Exception ex) { Console.WriteLine($"  Monitor.Pulse(lockAsObject) : {ex.GetType().Name}: {ex.Message}"); }

try { lock (real) { Monitor.Pulse(real); Console.WriteLine("  Monitor.Pulse(lock)         : ok"); } }
catch (Exception ex) { Console.WriteLine($"  Monitor.Pulse(lock)         : {ex.GetType().Name}: {ex.Message}"); }
```

```text
[monitor-api-on-lock]
  Monitor.Pulse(lockAsObject) : ok
  Monitor.Pulse(lock)         : SynchronizationLockException: Object synchronization method was called from an unsynchronized block of code.
```

That exception is a feature. It is the type system telling you that `Lock` is not a monitor and refuses to pretend.

## So is it actually faster?

This is the question the internet answers with a confident yes. I measured it with a best-of-five loop, twenty million enter/exit pairs per run, on an eight-core machine:

```csharp
public static void Uncontended()
{
    object monitorGate = new();
    var lockGate = new Lock();
    long sink = 0;

    for (int i = 0; i < 2_000_000; i++) { lock (monitorGate) sink++; lock (lockGate) sink++; }

    Console.WriteLine("[uncontended] best of 5, 20M enter/exit pairs each");
    Console.WriteLine($"  lock(object)      : {Best(() => { for (int i = 0; i < 20_000_000; i++) lock (monitorGate) sink++; })} ms");
    Console.WriteLine($"  lock(Lock)        : {Best(() => { for (int i = 0; i < 20_000_000; i++) lock (lockGate) sink++; })} ms");
    Console.WriteLine($"  Lock.EnterScope() : {Best(() => { for (int i = 0; i < 20_000_000; i++) { using (lockGate.EnterScope()) sink++; } })} ms");
    Console.WriteLine($"  Monitor.Enter     : {Best(() => { for (int i = 0; i < 20_000_000; i++) { Monitor.Enter(monitorGate); sink++; Monitor.Exit(monitorGate); } })} ms");
}

static long Best(Action a)
{
    long best = long.MaxValue;
    for (int run = 0; run < 5; run++)
    {
        var sw = Stopwatch.StartNew();
        a();
        best = Math.Min(best, sw.ElapsedMilliseconds);
    }
    return best;
}
```

```text
[uncontended] best of 5, 20M enter/exit pairs each
  lock(object)      : 400 ms
  lock(Lock)        : 407 ms
  Lock.EnterScope() : 410 ms
  Monitor.Enter     : 402 ms
```

Uncontended, the old way wins by seven milliseconds across twenty million locks. That is noise, and if anything it leans the wrong way for the new type.

Under contention, four threads fighting over one gate:

```csharp
Console.WriteLine($"  lock(object) : {Best(() => Race(threads, () => { for (int i = 0; i < perThread; i++) lock (monitorGate) counter++; }))} ms");
Console.WriteLine($"  lock(Lock)   : {Best(() => Race(threads, () => { for (int i = 0; i < perThread; i++) lock (lockGate) counter++; }))} ms");
```

```text
[contended] 4 threads x 2,000,000 increments, best of 5
  lock(object) : 288 ms
  lock(Lock)   : 270 ms
```

I ran that three more times to make sure I was not reading tea leaves:

```text
  lock(object) : 267 ms      lock(Lock) : 253 ms
  lock(object) : 281 ms      lock(Lock) : 284 ms
  lock(object) : 299 ms      lock(Lock) : 286 ms
```

Once the two runs cross over, you are looking at noise, not a win. **On this machine, migrating to `Lock` bought me no measurable speed.** Maybe a machine with more cores and nastier contention tells a different story. Mine did not, and neither will most business apps.

So migrate for the type safety, not for a benchmark you have not run.

## What you actually gain

The real payoff is an API surface that `object` never had. Reflection over the type, printed rather than remembered:

```csharp
foreach (var m in typeof(Lock).GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly))
{
    var sig = string.Join(", ", Array.ConvertAll(m.GetParameters(), p => $"{Pretty(p.ParameterType)} {p.Name}"));
    Console.WriteLine($"  {Pretty(m.ReturnType),-12} {m.Name}({sig})");
}
```

```text
[public API of System.Threading.Lock]
  void         Enter()
  Scope        EnterScope()
  bool         TryEnter()
  bool         TryEnter(int millisecondsTimeout)
  bool         TryEnter(TimeSpan timeout)
  void         Exit()
  bool         get_IsHeldByCurrentThread()
```

`TryEnter` with a timeout is the one I keep reaching for. Here it is against a gate another thread is holding for 400 ms:

```csharp
var gate = new Lock();
var holder = new Thread(() => { using (gate.EnterScope()) Thread.Sleep(400); });
holder.Start();
Thread.Sleep(50);
Console.WriteLine($"  gate.TryEnter(0)             : {gate.TryEnter(0)}");
Console.WriteLine($"  gate.TryEnter(1000)          : {gate.TryEnter(1000)}");
gate.Exit();
```

```text
[TryEnter with a timeout - the thing object could never do cleanly]
  gate.TryEnter(0)             : False
  gate.TryEnter(1000)          : True
```

Give up immediately, or wait up to a second. No `Monitor.TryEnter(obj, timeout, ref bool)` dance.

## IDE0330 will not nag you unless you ask

The advice you will read is that the analyzer flags every old `object` lock for you. It does, but only after you turn it on. Setting `EnforceCodeStyleInBuild` alone was not enough in my lab:

```bash
dotnet build -c Release --no-incremental 2>&1 | grep -c IDE0330
```

```text
0
```

Zero hits, on a file that is nothing but an old-style lock. IDE0330 ships as a suggestion, and suggestions do not survive a command-line build. Add the severity explicitly:

```ini
# .editorconfig
[*.cs]
dotnet_diagnostic.IDE0330.severity = warning
```

```bash
dotnet build -c Release
```

```text
Legacy.cs(3,29): warning IDE0330: Use 'System.Threading.Lock'
(https://learn.microsoft.com/dotnet/fundamentals/code-analysis/style-rules/ide0330)
```

Now it is in the build log, and now CI can see it.

## The co-star: params ReadOnlySpan

The other C# 13 feature worth your time is `params` on collection types. The pitch is that `params int[]` allocates an array on every call and `params ReadOnlySpan<int>` allocates nothing. I measured it with the thread's own allocation counter:

```csharp
static long MeasureBytes(Action a, int iterations)
{
    GC.Collect(); GC.WaitForPendingFinalizers(); GC.Collect();
    long before = GC.GetAllocatedBytesForCurrentThread();
    for (int i = 0; i < iterations; i++) a();
    return GC.GetAllocatedBytesForCurrentThread() - before;
}

[MethodImpl(MethodImplOptions.NoInlining)]
static int SumArray(params int[] values) { int s = 0; foreach (var v in values) s += v; return s; }

[MethodImpl(MethodImplOptions.NoInlining)]
static int SumSpan(params ReadOnlySpan<int> values) { int s = 0; foreach (var v in values) s += v; return s; }

Console.WriteLine($"  params int[]              : {MeasureBytes(() => SumArray(1, 2, 3), 1000)} bytes / 1000 calls");
Console.WriteLine($"  params ReadOnlySpan<int>  : {MeasureBytes(() => SumSpan(1, 2, 3), 1000)} bytes / 1000 calls");
Console.WriteLine($"  span, non-constant args   : {MeasureBytes(() => SumSpanVariable(Environment.TickCount, 2, 3), 1000)} bytes / 1000 calls");
Console.WriteLine($"  span, zero args           : {MeasureBytes(() => SumSpan(), 1000)} bytes / 1000 calls");
Console.WriteLine($"  array, zero args          : {MeasureBytes(() => SumArray(), 1000)} bytes / 1000 calls");
```

```text
[params-allocations]
  params int[]              : 112000 bytes / 1000 calls
  params ReadOnlySpan<int>  : 0 bytes / 1000 calls
  span, non-constant args   : 0 bytes / 1000 calls
  span, zero args           : 0 bytes / 1000 calls
  array, zero args          : 0 bytes / 1000 calls
```

112 bytes per call for three integers, versus nothing. That claim holds up completely.

Note the last line though: the **array** version also allocates nothing when you pass no arguments, because the compiler hands it `Array.Empty<int>()`. The allocation only appears once there is something to put in the array.

### It is not stackalloc

Almost every write-up says the compiler uses `stackalloc` under the hood. I went looking for the `localloc` instruction in the IL and could not find one, because there isn't one. There are two different mechanisms, and neither is `stackalloc`.

For constant arguments, the span points at a blob of read-only data baked into the assembly:

```csharp
public int CallArray() => SumArray(12, 45, 89);
public int CallSpan() => SumSpan(12, 45, 89);
```

```text
CallArray:
  IL_0001: newarr [System.Runtime]System.Int32
  IL_000c: call void ...RuntimeHelpers::InitializeArray(class Array, valuetype RuntimeFieldHandle)
  IL_0011: call int32 Lowering::SumArray(int32[])

CallSpan:
  IL_0000: ldtoken field valuetype '<PrivateImplementationDetails>'/'__StaticArrayInitTypeSize=12_Align=4' ...
  IL_0005: call valuetype ReadOnlySpan`1<!!0> ...RuntimeHelpers::CreateSpan<int32>(valuetype RuntimeFieldHandle)
  IL_000a: call int32 Lowering::SumSpan(valuetype ReadOnlySpan`1<int32>)
```

There is the `newarr` in the array version, and there is no allocation at all in the span version. Three IL instructions, pointing at data that was already in the file.

For arguments the compiler cannot precompute, it uses an inline array struct living in the stack frame:

```csharp
public int CallSpanVariable(int a, int b, int c) => SumSpan(a, b, c);
```

```text
.locals init (
  [0] valuetype '<>y__InlineArray3`1'<int32>
)
IL_0002: initobj valuetype '<>y__InlineArray3`1'<int32>
...
IL_0029: call valuetype ReadOnlySpan`1<!!1>
         '<PrivateImplementationDetails>'::InlineArrayAsReadOnlySpan<...>(!!0&, int32)
```

A local struct, zeroed and filled in place. Practically speaking it lives on the stack, so "no heap allocation" is true. But if you go hunting for `stackalloc` to confirm what you read, you will not find it.

### Adding the overload moves your call sites

One last thing that surprised me. If you add a `ReadOnlySpan` overload next to an existing array one, expecting old callers to carry on as before, they will not:

```csharp
public class Overloads
{
    public static string Which(params int[] v) => "array overload";
    public static string Which(params ReadOnlySpan<int> v) => "span overload";
}

Console.WriteLine($"Which(1, 2, 3)          -> {Overloads.Which(1, 2, 3)}");
Console.WriteLine($"Which(new[]{{1, 2, 3}})   -> {Overloads.Which(new[] { 1, 2, 3 })}");
Console.WriteLine($"Which()                 -> {Overloads.Which()}");
```

```text
Which(1, 2, 3)          -> span overload
Which(new[]{1, 2, 3})   -> array overload
Which()                 -> span overload
```

The span overload quietly wins every call site that passes loose arguments. That is exactly what you want for performance and exactly what you must not ignore if the two overloads ever behave differently. Only callers passing an actual array keep the old path.

## Summary

* **`lock` only uses the new fast path when the static type is `Lock`.** Cast it to `object` and you silently get a plain monitor instead, with no mutual exclusion between the two styles. I measured 44,287 overlapping critical sections.
* **Make CS9216 an error in your build.** It is the compiler warning you about exactly that footgun.
* **Do not migrate for speed.** Uncontended, `lock (object)` measured 400 ms against 407 ms for `lock (Lock)`. Contended, the two traded places run to run.
* **Migrate for the API**: `TryEnter` with a timeout, `IsHeldByCurrentThread`, and a `SynchronizationLockException` when someone treats your lock like a monitor.
* **IDE0330 is a suggestion**, invisible in a command-line build until you set its severity in `.editorconfig`.
* **`params ReadOnlySpan<T>` really is zero bytes**, but through a static data blob or an inline array struct, not `stackalloc`.
* **Adding a span overload steals call sites** from the array overload. Fine when they agree, a bug when they do not.

Friendly closing tip: before you run that solution-wide replace of `object` with `Lock`, grep for every place the lock leaves its home class. The fields are easy. It is the helper method that takes an `object` parameter that will quietly undo the whole migration.
