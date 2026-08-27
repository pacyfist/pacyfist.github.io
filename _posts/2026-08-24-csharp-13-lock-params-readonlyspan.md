---
# SEO Target Queries:
#   Google: "c# new lock object", "c# 13 lock", "system.threading.lock", "c# params readonlyspan"
#   Bing:   "c# new lock object", "c# 13 params collections", "c# lock vs monitor"
tags: ["csharp", "dotnet", "concurrency", "performance", "csharp13"]
categories: ["csharp", "dotnet"]
title: "C# 13 Lock + params ReadOnlySpan: One Trap, One Win"
image:
  path: /assets/img/2026-08-24/main.jpg
  alt: Two doors into the same room, and only one of them has a lock that works.
published: false
---

I planned this post around one claim: that `System.Threading.Lock` is faster than the `private readonly object _lock = new();` it replaces. Then the benchmark printed 398 ms for `lock (object)` and 405 ms for `lock (Lock)` over twenty million locks. Seven milliseconds, and the wrong way round. Two runs later they had swapped places.

Working out why took a console project, a disassembler and a stopwatch, and it turned up something worse than a flat benchmark: a way to write `lock` that does not lock.

The same lab answered a second C# 13 question while it was open, and the two answers belong together. Both features work the same way underneath: **the compiler looks at the static type you wrote and picks a shape.** For `lock` that rule is a trap. For `params ReadOnlySpan<int>` it is a real, measurable win. Both shipped with C# 13 and .NET 9, so neither is new any more. This post is the trap first, then the win.

## A console project and a disassembler

Everything runs on the stable SDK, nothing preview:

```bash
dotnet --version
```

```text
10.0.111
```

The lab is not one project but a handful of small ones: a console app that runs the probes and the benchmarks, a class library I disassemble, a third for the analyzer, and two more for the overload and API questions. They all share these two lines:

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

The SDK is 10.0.111 and the runtime it targets is 10.0.11. Two different version lines, not a typo.

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

Build it and disassemble. `ilspycmd` is a global tool, so install it first if you have not:

```bash
dotnet tool install -g ilspycmd
dotnet build -c Release
ilspycmd -il bin/Release/net10.0/illab.dll
```

That prints the whole assembly, which is a few hundred lines. The interesting parts are quoted below. Every IL block in this post is an excerpt of that one dump. Lines I left out are marked with `...` on its own line, and the tabs the tool indents with are turned into spaces. Inside a line nothing is edited, assembly qualifiers included, so some of them are long.

`OldStyle` is the shape we have all known for twenty years, a `Monitor.Enter` with a bool flag and a `finally` that calls `Monitor.Exit`:

```text
...
.try
{
  IL_0009: ldloc.0
  IL_000a: ldloca.s 1
  IL_000c: call void [System.Threading]System.Threading.Monitor::Enter(object, bool&)
  ...
  IL_001f: leave.s IL_002b
} // end .try
finally
{
  IL_0021: ldloc.1
  IL_0022: brfalse.s IL_002a

  IL_0024: ldloc.0
  IL_0025: call void [System.Threading]System.Threading.Monitor::Exit(object)

  IL_002a: endfinally
} // end handler
...
```

`NewStyle` is a different animal entirely:

```text
...
IL_0006: callvirt instance valuetype [System.Runtime]System.Threading.Lock/Scope [System.Runtime]System.Threading.Lock::EnterScope()
IL_000b: stloc.0
.try
{
  ...
  IL_001a: leave.s IL_0024
} // end .try
finally
{
  IL_001c: ldloca.s 0
  IL_001e: call instance void [System.Runtime]System.Threading.Lock/Scope::Dispose()
  IL_0023: endfinally
} // end handler
...
```

The listing gives away two things at once. The `Dispose` is a plain `call`, not a `callvirt`, so there is no interface dispatch. And the whole method is smaller. The listing's header comments read `Code size: 44 (0x2c)` for `OldStyle` and `Code size: 37 (0x25)` for `NewStyle`. One local variable instead of two.

That `Scope` really is a `ref struct`, and it really does not implement `IDisposable`:

```csharp
var scopeType = typeof(Lock.Scope);
Console.WriteLine("[scope-type]");
Console.WriteLine($"  full name    : {scopeType.FullName}");
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

The `using` block works through pattern-based disposal instead of the interface. That is why the `Dispose` is a plain `call` with no boxing and no interface dispatch.

## The trap: one assignment and your lock stops locking

This is where the post I planned fell apart.

The compiler only emits `EnterScope()` when the **static type** at the `lock` keyword is `Lock`. Assign that same object to an `object` variable, and `lock` falls straight back to `Monitor`. Both lines look correct. They lock two completely different things.

```csharp
var real = new Lock();
object asObject = real;

Console.WriteLine("[static-type-matters]");
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
Console.WriteLine("[mutual-exclusion-across-static-types]");
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
  overlapping critical sections observed : 11352
```

Eleven thousand times in that run, both threads were inside the critical section at once. The lock was doing nothing.

That number is the outcome of a race, so it is worth knowing how much it wanders before anyone quotes it. I put the exact same block in a loop, on a fresh `Lock` each trial:

```csharp
for (int trial = 1; trial <= 10; trial++)
{
    // ... the two threads above, verbatim, on a new gate every time
    Console.WriteLine($"  trial {trial,2} : overlapping critical sections observed : {overlaps}");
}
```

```text
  trial  1 : overlapping critical sections observed : 39018
  trial  2 : overlapping critical sections observed : 78388
  trial  3 : overlapping critical sections observed : 47695
  trial  4 : overlapping critical sections observed : 51992
  trial  5 : overlapping critical sections observed : 28148
  trial  6 : overlapping critical sections observed : 58339
  trial  7 : overlapping critical sections observed : 51460
  trial  8 : overlapping critical sections observed : 16489
  trial  9 : overlapping critical sections observed : 59245
  trial 10 : overlapping critical sections observed : 102624
```

In these ten trials the count ran from sixteen thousand to a hundred thousand. Across every run I did it went as low as about three thousand and as high as a hundred and twenty thousand. **The number is meaningless and the fact is not: it is never zero.**

The same split shows up in the `Monitor` API. Call `Monitor.Pulse` on the object-typed reference and it works, because that is a plain monitor. Call it on the `Lock`, and it throws:

```csharp
Console.WriteLine("[monitor-api-on-lock]");
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

### The compiler already told me, three times

None of this is a secret the compiler keeps. It ships a dedicated diagnostic for exactly this conversion, and Microsoft documents the behaviour on the CS9216 page in the C# language reference. My lab build produced it three times without me asking for anything:

```bash
dotnet build -c Release --no-incremental 2>&1 | grep -o "Program.cs.*statement\." | sort -u
```

```text
Program.cs(20,19): warning CS9216: A value of type 'System.Threading.Lock' converted to a different type will use likely unintended monitor-based locking in 'lock' statement.
Program.cs(36,23): warning CS9216: A value of type 'System.Threading.Lock' converted to a different type will use likely unintended monitor-based locking in 'lock' statement.
Program.cs(62,33): warning CS9216: A value of type 'System.Threading.Lock' converted to a different type will use likely unintended monitor-based locking in 'lock' statement.
```

(The `grep` is only there to strip the absolute paths off the front and the `[...csproj]` off the back. The real lines are longer.)

So the trap is not silent. It is a **warning in a build log**, which in a solution of any size is the same as silent by lunchtime. And it fires at the conversion, on line 20, not at the `lock` on line 27 where the damage happens.

Store a `Lock` in an `object` field. Pass it to a helper that takes `object`. Drop it into a `List<object>`. In every one of those you keep the syntax and lose the guarantee. So I wrote a probe with all three in one file, to find out whether any of them gets past the compiler:

```csharp
using System.Threading;

// Probe: the three ordinary ways a Lock escapes into an object.
// Question: does CS9216 fire at each of these escape routes,
// or does one of them slip through with no diagnostic at all?
// (Silent.cs holds two more exotic routes.)

var gate = new Lock();

Helper.LockIt(gate);                 // 1. passed to a helper taking object
var holder = new Holder(gate);       // 2. stored in an object-typed field via ctor
holder.LockIt();
var list = new List<object> { gate };// 3. dropped into a List<object>
lock (list[0]) { }                   // 4. locked out of that list
Console.WriteLine("probe compiled and ran");

static class Helper
{
    public static void LockIt(object o) { lock (o) { } }   // no Lock in sight here
}

class Holder
{
    private readonly object _gate;
    public Holder(Lock l) { _gate = l; }
    public void LockIt() { lock (_gate) { } }
}
```

```bash
dotnet build -c Release --no-incremental 2>&1 | grep -o "[A-Za-z]*\.cs([0-9,]*): warning CS9216" | sort -u
```

```text
Program.cs(10,15): warning CS9216
Program.cs(13,31): warning CS9216
Program.cs(25,37): warning CS9216
Silent.cs(7,40): warning CS9216
```

Three of those are the three routes above, each caught at the exact line that does the conversion: the call on line 10, the list initializer on line 13, the constructor on line 25. **Grepping your codebase for the escape routes is the wrong tool, because the compiler already found them.** Make it stop the build instead:

```xml
<WarningsAsErrors>CS9216</WarningsAsErrors>
```

```bash
dotnet build -c Release --no-incremental -p:WarningsAsErrors=CS9216 2>&1 | grep -o -E "[A-Za-z]*\.cs\([0-9,]*\): error CS9216|[0-9]+ Error\(s\)" | sort -u
```

```text
4 Error(s)
Program.cs(10,15): error CS9216
Program.cs(13,31): error CS9216
Program.cs(25,37): error CS9216
Silent.cs(7,40): error CS9216
```

### The one route the compiler cannot see

That last warning came from a second file in the same probe, and that file exists to answer the obvious next question: is there any way to turn a `Lock` into an `object` that CS9216 misses? There is exactly one I could find.

```csharp
using System.Threading;

// Is there any route where a Lock becomes an object WITHOUT CS9216?
public static class Silent
{
    // a) factory that returns object
    public static object MakeGate() => new Lock();

    // b) generic pass-through
    public static object Box<T>(T t) where T : class => t;

    public static void Use()
    {
        object g1 = MakeGate();
        lock (g1) { }                       // no warning possible: static type is object

        var real = new Lock();
        object g2 = Box(real);              // does the generic hop hide it?
        lock (g2) { }
    }
}
```

```bash
dotnet build -c Release --no-incremental 2>&1 | grep -o "Silent.cs([0-9,]*): warning CS9216" | sort -u
```

```text
Silent.cs(7,40): warning CS9216
```

One warning, and it is on line 7. The factory gets caught, because `new Lock()` converting to an `object` return type is a conversion the compiler can see. **Line 18 gets nothing.** Inside `Box<T>`, `T` is just some reference type, so there is no `Lock`-shaped conversion to warn about, and by the time the value comes back out it is already an `object`.

That is the genuinely quiet one. A generic helper, a DI container resolving to `object`, anything that launders the type through a type parameter. No warning, no error, and a `lock` that has stopped locking.

### IDE0330 will not nag you unless you ask

There is a second analyzer pointed the other way: IDE0330 finds your old `object` locks and suggests migrating them. It does nothing until you turn it on, which is worth knowing before you trust a clean build log as proof that you have no old locks left. The whole project I pointed it at is this:

```csharp
public class Legacy
{
    private readonly object _lock = new();
    private int _n;
    public void Bump() { lock (_lock) { _n++; } }
}
```

It already had the code-style switches set in the csproj:

```xml
<EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>
<AnalysisLevel>latest</AnalysisLevel>
```

And that alone still found nothing:

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
dotnet build -c Release --no-incremental 2>&1 | grep -o "Legacy.cs.*ide0330)" | sort -u
```

```text
Legacy.cs(3,29): warning IDE0330: Use 'System.Threading.Lock' (https://learn.microsoft.com/dotnet/fundamentals/code-analysis/style-rules/ide0330)
```

Now it is in the build log, and now CI can see it.

## So is it actually faster?

The static-type rule decides whether your lock locks at all. It has nothing to say about how fast it locks, and speed was the claim this post started with. So back to that claim, which the internet answers with a confident yes. I measured it with a best-of-five loop, twenty million enter/exit pairs per run, on a four-core, eight-thread i7-3770K:

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
    Console.WriteLine($"  (sink={sink})");
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
  lock(object)      : 398 ms
  lock(Lock)        : 405 ms
  Lock.EnterScope() : 405 ms
  Monitor.Enter     : 394 ms
  (sink=404000000)
```

That is one run. I did four, and the ordering did not survive them. Here are the other three, pasted one after another:

```text
[uncontended] best of 5, 20M enter/exit pairs each
  lock(object)      : 400 ms
  lock(Lock)        : 403 ms
  Lock.EnterScope() : 403 ms
  Monitor.Enter     : 396 ms
  (sink=404000000)
[uncontended] best of 5, 20M enter/exit pairs each
  lock(object)      : 399 ms
  lock(Lock)        : 394 ms
  Lock.EnterScope() : 395 ms
  Monitor.Enter     : 398 ms
  (sink=404000000)
[uncontended] best of 5, 20M enter/exit pairs each
  lock(object)      : 397 ms
  lock(Lock)        : 389 ms
  Lock.EnterScope() : 400 ms
  Monitor.Enter     : 420 ms
  (sink=404000000)
```

Across those four, `lock (object)` landed between 397 and 400 ms, `lock (Lock)` between 389 and 405, `Lock.EnterScope()` between 395 and 405, and `Monitor.Enter` between 394 and 420. Two of the four runs put the new lock ahead. Two put it behind. **The gap between the two moves more from run to run than the two differ from each other**, which is the shape of noise, not of a win. That is one machine on one afternoon. Yours will draw the line somewhere else.

Under contention, four threads fighting over one gate:

```csharp
public static void Contended(int threads = 4, int perThread = 2_000_000)
{
    object monitorGate = new();
    var lockGate = new Lock();
    long counter = 0;

    Console.WriteLine($"[contended] {threads} threads x {perThread:N0} increments, best of 5");
    Console.WriteLine($"  lock(object) : {Best(() => Race(threads, () => { for (int i = 0; i < perThread; i++) lock (monitorGate) counter++; }))} ms");
    Console.WriteLine($"  lock(Lock)   : {Best(() => Race(threads, () => { for (int i = 0; i < perThread; i++) lock (lockGate) counter++; }))} ms");
    Console.WriteLine($"  (counter={counter})");
}

static void Race(int threads, Action body)
{
    var ts = new Thread[threads];
    for (int i = 0; i < threads; i++) { ts[i] = new Thread(() => body()); ts[i].Start(); }
    foreach (var t in ts) t.Join();
}
```

```text
[contended] 4 threads x 2,000,000 increments, best of 5
  lock(object) : 268 ms
  lock(Lock)   : 274 ms
  (counter=80000000)
```

Here is the same block from the other three runs of the program, pasted one after another:

```text
[contended] 4 threads x 2,000,000 increments, best of 5
  lock(object) : 273 ms
  lock(Lock)   : 287 ms
  (counter=80000000)
[contended] 4 threads x 2,000,000 increments, best of 5
  lock(object) : 261 ms
  lock(Lock)   : 270 ms
  (counter=80000000)
[contended] 4 threads x 2,000,000 increments, best of 5
  lock(object) : 246 ms
  lock(Lock)   : 276 ms
  (counter=80000000)
```

The old lock is ahead in all four here, by 6 to 30 ms. Its own column wanders 27 ms between its best run and its worst, so the gap between the columns is about the size of the noise inside one of them. **On this machine, migrating to `Lock` bought me no measurable speed.** Maybe a machine with more cores and nastier contention tells a different story. Mine did not, and neither will most business apps.

So migrate for the type safety, not for a benchmark you have not run.

## What you actually gain

The real payoff is an API surface that `object` never had. Reflection prints the whole surface, so here it is:

```csharp
using System.Reflection;

Console.WriteLine("[public API of System.Threading.Lock]");
foreach (var m in typeof(Lock).GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly))
{
    var sig = string.Join(", ", Array.ConvertAll(m.GetParameters(), p => $"{Pretty(p.ParameterType)} {p.Name}"));
    Console.WriteLine($"  {Pretty(m.ReturnType),-12} {m.Name}({sig})");
}

static string Pretty(Type t) => t.Name switch
{
    "Void" => "void", "Boolean" => "bool", "Int32" => "int", _ => t.Name
};
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

`TryEnter` with a timeout is the one that changes how you write contention handling, because with a plain `object` it needed `Monitor.TryEnter(obj, timeout, ref bool)` and a `finally`. Here it is against a gate another thread is holding for 400 ms:

```csharp
Console.WriteLine("[TryEnter with a timeout - the thing object could never do cleanly]");
var gate = new Lock();
var holder = new Thread(() => { using (gate.EnterScope()) Thread.Sleep(400); });
holder.Start();
Thread.Sleep(50);
Console.WriteLine($"  gate.TryEnter(0)             : {gate.TryEnter(0)}");
Console.WriteLine($"  gate.TryEnter(1000)          : {gate.TryEnter(1000)}");
gate.Exit();
holder.Join();
```

```text
[TryEnter with a timeout - the thing object could never do cleanly]
  gate.TryEnter(0)             : False
  gate.TryEnter(1000)          : True
```

Give up immediately, or wait up to a second. No `ref bool` dance.

## The win: params ReadOnlySpan

Same rule, opposite outcome.

`lock` picks its shape from the static type at the keyword, and that is the trap. `params` picks its shape from the static type of the parameter you declared, and that one pays you back. Nothing here can stop working behind your back, because there is no second type for the value to leak into.

The pitch is that `params int[]` allocates an array on every call and `params ReadOnlySpan<int>` allocates nothing. That is a number, so it can be measured, and I measured it with the thread's own allocation counter:

```csharp
Console.WriteLine("[params-allocations]");
// Warm up the DELEGATES, not just the methods. MeasureBytes calls through an
// Action, so if the lambda is still at tier-0 the measurement bills you for
// the JIT tier, not for the params array.
Action arrayCall   = () => SumArray(1, 2, 3);
Action spanCall    = () => SumSpan(1, 2, 3);
Action spanVarCall = () => SumSpanVariable(Environment.TickCount, 2, 3);
Action spanZero    = () => SumSpan();
Action arrayZero   = () => SumArray();
for (int i = 0; i < 200_000; i++) { arrayCall(); spanCall(); spanVarCall(); spanZero(); arrayZero(); }
Thread.Sleep(500);
for (int i = 0; i < 200_000; i++) { arrayCall(); spanCall(); spanVarCall(); spanZero(); arrayZero(); }

Console.WriteLine($"  params int[]              : {MeasureBytes(arrayCall, 1000)} bytes / 1000 calls");
Console.WriteLine($"  params ReadOnlySpan<int>  : {MeasureBytes(spanCall, 1000)} bytes / 1000 calls");
Console.WriteLine($"  span, non-constant args   : {MeasureBytes(spanVarCall, 1000)} bytes / 1000 calls");
Console.WriteLine($"  span, zero args           : {MeasureBytes(spanZero, 1000)} bytes / 1000 calls");
Console.WriteLine($"  array, zero args          : {MeasureBytes(arrayZero, 1000)} bytes / 1000 calls");

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

[MethodImpl(MethodImplOptions.NoInlining)]
static int SumSpanVariable(params ReadOnlySpan<int> values) { int s = 0; foreach (var v in values) s += v; return s; }
```

```text
[params-allocations]
  params int[]              : 40000 bytes / 1000 calls
  params ReadOnlySpan<int>  : 0 bytes / 1000 calls
  span, non-constant args   : 0 bytes / 1000 calls
  span, zero args           : 0 bytes / 1000 calls
  array, zero args          : 0 bytes / 1000 calls
```

**40 bytes per call for three integers, versus nothing.** And 40 is not a mystery number: it is exactly one `int[3]` on 64-bit. Twenty-four bytes of object header and length, twelve bytes of payload, rounded up to the eight-byte alignment.

### The warm-up loop is not decoration

That comment about warming the delegates is the whole reason the number above says 40. My first version of that loop warmed `SumArray` and `SumSpan` directly, but `MeasureBytes` does not call them directly. It calls them through an `Action`, and a lambda invoked a thousand times never leaves tier-0. The counter read **112 bytes per call** and I nearly published that as the cost of `params int[]`.

It is not. It is 40 bytes of array plus 72 bytes of JIT bookkeeping, charged to the feature by mistake. Here is the probe that separates them, with a do-nothing method as the control:

```csharp
Action arrayCall = () => SumArray(1, 2, 3);
Action spanCall  = () => SumSpan(1, 2, 3);
Action nothing   = () => Nothing();

Console.WriteLine("--- cold (post's shape: lambda invoked 1000x from tier-0) ---");
Console.WriteLine($"  delegate -> SumArray  : {Measure(arrayCall, 1000)}");
Console.WriteLine($"  delegate -> SumSpan   : {Measure(spanCall, 1000)}");
Console.WriteLine($"  delegate -> Nothing   : {Measure(nothing, 1000)}");

Console.WriteLine("--- after 200k invocations of each delegate (fully tiered up) ---");
for (int i = 0; i < 200_000; i++) { arrayCall(); spanCall(); nothing(); }
Thread.Sleep(500);
for (int i = 0; i < 200_000; i++) { arrayCall(); spanCall(); nothing(); }
Console.WriteLine($"  delegate -> SumArray  : {Measure(arrayCall, 1000)}");
Console.WriteLine($"  delegate -> SumSpan   : {Measure(spanCall, 1000)}");
Console.WriteLine($"  delegate -> Nothing   : {Measure(nothing, 1000)}");

static string Measure(Action a, int n)
{
    GC.Collect(); GC.WaitForPendingFinalizers(); GC.Collect();
    long before = GC.GetAllocatedBytesForCurrentThread();
    for (int i = 0; i < n; i++) a();
    long total = GC.GetAllocatedBytesForCurrentThread() - before;
    return $"{total} bytes / {n} calls = {total / (double)n} per call";
}

[MethodImpl(MethodImplOptions.NoInlining)]
static int SumArray(params int[] values) { int s = 0; foreach (var v in values) s += v; return s; }
[MethodImpl(MethodImplOptions.NoInlining)]
static int SumSpan(params ReadOnlySpan<int> values) { int s = 0; foreach (var v in values) s += v; return s; }
[MethodImpl(MethodImplOptions.NoInlining)]
static int Nothing() => 7;
```

```text
--- cold (post's shape: lambda invoked 1000x from tier-0) ---
  delegate -> SumArray  : 112000 bytes / 1000 calls = 112 per call
  delegate -> SumSpan   : 0 bytes / 1000 calls = 0 per call
  delegate -> Nothing   : 0 bytes / 1000 calls = 0 per call
--- after 200k invocations of each delegate (fully tiered up) ---
  delegate -> SumArray  : 40000 bytes / 1000 calls = 40 per call
  delegate -> SumSpan   : 0 bytes / 1000 calls = 0 per call
  delegate -> Nothing   : 0 bytes / 1000 calls = 0 per call
```

Same code, same process, 112 then 40. **If a micro-benchmark runs its work through a delegate, warm the delegate, not the method.** The zero for the span is the same either way, which is what makes it trustworthy.

### The array version allocates nothing when it is empty

Look at the last line of that measurement again: the **array** version also allocates nothing when you pass no arguments. The post's method is to read the IL rather than to guess, so here is a class with nothing in it but that call, and what `CallArrayEmpty` lowers to:

```csharp
public class Lowering3
{
    public int CallArrayEmpty() => SumArray();

    private static int SumArray(params int[] v) => v.Length;
}
```

```text
.method public hidebysig 
  instance int32 CallArrayEmpty () cil managed 
{
  ...
  // Code size: 11 (0xb)
  .maxstack 8

  IL_0000: call !!0[] [System.Runtime]System.Array::Empty<int32>()
  IL_0005: call int32 Lowering3::SumArray(int32[])
  IL_000a: ret
} // end of method Lowering3::CallArrayEmpty
```

`Array.Empty<int>()`, a cached singleton. The allocation only appears once there is something to put in the array.

### It is not stackalloc

The usual one-line explanation is that the compiler uses `stackalloc` under the hood. It does not. The IL instruction behind `stackalloc` is `localloc`, and there is not one in the whole assembly:

```bash
ilspycmd -il bin/Release/net10.0/illab.dll | grep -c localloc
```

```text
0
```

There are two different mechanisms, and neither is `stackalloc`. For constant arguments, the span points at a blob of read-only data baked into the assembly. Here are two more methods on the same `Lowering` class from earlier, with the lock ones left out:

```csharp
public class Lowering
{
    public int CallArray() => SumArray(12, 45, 89);
    public int CallSpan() => SumSpan(12, 45, 89);

    private static int SumArray(params int[] v) => v.Length;
    private static int SumSpan(params System.ReadOnlySpan<int> v) => v.Length;
}
```

`ilspycmd` prints those two methods one after the other, `CallArray` first, and the excerpt keeps them in that order. The `...` under each `{` is where the `// Method begins at RVA` and `// Header size` comments were, because the address moves on every build:

```text
.method public hidebysig 
  instance int32 CallArray () cil managed 
{
  ...
  // Code size: 23 (0x17)
  .maxstack 8

  IL_0000: ldc.i4.3
  IL_0001: newarr [System.Runtime]System.Int32
  IL_0006: dup
  IL_0007: ldtoken field valuetype '<PrivateImplementationDetails>'/'__StaticArrayInitTypeSize=12' '<PrivateImplementationDetails>'::'5F992BB1CAF8353355352E514769E859324A1AEBBF26D5577DDE4CC77580B1C1'
  IL_000c: call void [System.Runtime]System.Runtime.CompilerServices.RuntimeHelpers::InitializeArray(class [System.Runtime]System.Array, valuetype [System.Runtime]System.RuntimeFieldHandle)
  IL_0011: call int32 Lowering::SumArray(int32[])
  IL_0016: ret
} // end of method Lowering::CallArray

.method public hidebysig 
  instance int32 CallSpan () cil managed 
{
  ...
  // Code size: 16 (0x10)
  .maxstack 8

  IL_0000: ldtoken field valuetype '<PrivateImplementationDetails>'/'__StaticArrayInitTypeSize=12_Align=4' '<PrivateImplementationDetails>'::'5F992BB1CAF8353355352E514769E859324A1AEBBF26D5577DDE4CC77580B1C14'
  IL_0005: call valuetype [System.Runtime]System.ReadOnlySpan`1<!!0> [System.Runtime]System.Runtime.CompilerServices.RuntimeHelpers::CreateSpan<int32>(valuetype [System.Runtime]System.RuntimeFieldHandle)
  IL_000a: call int32 Lowering::SumSpan(valuetype [System.Runtime]System.ReadOnlySpan`1<int32>)
  IL_000f: ret
} // end of method Lowering::CallSpan
```

There is the `newarr` in the array version, and there is no allocation at all in the span version. The header comments say it too: `Code size: 23 (0x17)` for `CallArray` against `Code size: 16 (0x10)` for `CallSpan`, and the span version is just pointing at data that was already in the file.

For arguments the compiler cannot precompute, it uses an inline array struct living in the stack frame:

```csharp
public class Lowering2
{
    public int CallSpanVariable(int a, int b, int c) => SumSpan(a, b, c);

    private static int SumSpan(params ReadOnlySpan<int> v) => v.Length;
}
```

The dump for that one method is 52 bytes of IL, and most of the middle is three near-identical writes into the struct. Those are the lines behind the second `...`:

```text
.method public hidebysig 
  instance int32 CallSpanVariable (
    int32 a,
    int32 b,
    int32 c
  ) cil managed 
{
  ...
  // Code size: 52 (0x34)
  .maxstack 2
  .locals init (
    [0] valuetype '<>y__InlineArray3`1'<int32>
  )

  IL_0000: ldloca.s 0
  IL_0002: initobj valuetype '<>y__InlineArray3`1'<int32>
  ...
  IL_0026: ldloca.s 0
  IL_0028: ldc.i4.3
  IL_0029: call valuetype [System.Runtime]System.ReadOnlySpan`1<!!1> '<PrivateImplementationDetails>'::InlineArrayAsReadOnlySpan<valuetype '<>y__InlineArray3`1'<int32>, int32>(!!0&, int32)
  IL_002e: call int32 Lowering2::SumSpan(valuetype [System.Runtime]System.ReadOnlySpan`1<int32>)
  IL_0033: ret
} // end of method Lowering2::CallSpanVariable
```

A local struct, zeroed and filled in place. Practically speaking it lives on the stack, so "no heap allocation" is true. But if you go hunting for `stackalloc` to confirm what you read, you will not find it.

### Adding the overload moves your call sites

One more consequence, and this is the sharp edge on the win. If you add a `ReadOnlySpan` overload next to an existing array one, expecting old callers to carry on as before, they will not:

```csharp
Console.WriteLine($"Which(1, 2, 3)          -> {Overloads.Which(1, 2, 3)}");
Console.WriteLine($"Which(new[]{{1, 2, 3}})   -> {Overloads.Which(new[] { 1, 2, 3 })}");
Console.WriteLine($"Which()                 -> {Overloads.Which()}");

public class Overloads
{
    public static string Which(params int[] v) => "array overload";
    public static string Which(params ReadOnlySpan<int> v) => "span overload";
}
```

```text
Which(1, 2, 3)          -> span overload
Which(new[]{1, 2, 3})   -> array overload
Which()                 -> span overload
```

The span overload quietly wins every call site that passes loose arguments. That is exactly what you want for performance and exactly what you must not ignore if the two overloads ever behave differently. Only callers passing an actual array keep the old path.

## Summary

* **`lock` only takes the fast path when the static type at the keyword is `Lock`.** Assign it to an `object` and you get a plain monitor, with no mutual exclusion between the two styles. My lab counted between about three thousand and a hundred and twenty thousand overlapping critical sections, depending on the run, and never zero.
* **The compiler does warn.** CS9216 fires at every direct conversion, at the assignment rather than at the `lock`. Set `<WarningsAsErrors>CS9216</WarningsAsErrors>` and it stops the build instead of scrolling past.
* **A generic pass-through is the one hole.** `Box<T>(T t) where T : class` hands you back an `object` with no warning anywhere.
* **IDE0330 is a suggestion**, invisible in a command-line build until you set its severity in `.editorconfig`.
* **Do not migrate for speed.** On this machine, over four runs of twenty million uncontended locks, `lock (object)` measured 397 to 400 ms and `lock (Lock)` 389 to 405 ms. They traded places twice. Contended, the old lock was ahead in all four, by 6 to 30 ms against a 27 ms wobble in its own column.
* **Migrate for the API**: `TryEnter` with a timeout, `IsHeldByCurrentThread`, and a `SynchronizationLockException` when someone treats your lock like a monitor.
* **`params ReadOnlySpan<int>` really is zero bytes**, against 40 for `params int[]` with three arguments, which is exactly one `int[3]`. Warm your delegates before you believe any number bigger than that.
* **It is not `stackalloc`.** Constant arguments come from a static data blob, variable ones from an inline array struct in the stack frame, and there is no `localloc` in the IL.
* **Adding a span overload steals call sites** from the array overload. Fine when the two agree, a bug when they do not.

Before you run that solution-wide replace of `object` with `Lock`, add `<WarningsAsErrors>CS9216</WarningsAsErrors>` to the project and build once. The compiler will stop you at every conversion it can see, which is nearly all of them. Then go and read your generic helpers by hand, because a `Box<T>` sitting between the `Lock` and the `lock` is the one thing it cannot.
