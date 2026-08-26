---
# SEO Target Queries:
#   Google: "c# new lock object", "c# 13 params collections", "c# params readonlyspan"
#   Bing:   "c# new lock object", "csharp async await common pitfalls"
tags: ["csharp", "dotnet", "concurrency", "performance", "csharp13"]
categories: ["csharp", "dotnet"]
title: "C# 13 Lock Object: Why new object() is Officially Obsolete"
published: false
---

Open any C# codebase on GitHub written between 2002 and last year. Search for `_lock`. You will see this line thousands of times:

```csharp
private readonly object _lock = new();
```

For over two decades, `new object()` was the standard idiom for thread synchronization in C#. We allocated a generic heap object solely for its 8-byte sync block index in the object header, and called `lock (_lock)`.

With C# 13 and .NET 9, Microsoft introduced `System.Threading.Lock`, backed by compiler support and code analyzer **IDE0330**.

If you upgrade your project to .NET 9, your IDE will flag that `new object()` and politely suggest you replace it. Here is what actually changes under the hood, why it performs better, and why `params ReadOnlySpan<T>` is the quiet co-star of this release.

## What's Wrong with `new object()`?

Using `object` for synchronization had several architectural flaws:

1. **Lack of Type Safety:** Any code with access to the reference could `Monitor.Pulse`, `Monitor.Wait`, or accidentally lock on it from somewhere else.
2. **Sync Block Overhead:** In the CLR, normal objects don't allocate synchronization primitives until contended. When you lock on an object, the runtime lazily assigns or inflates a sync block entry in a global table.
3. **No RAII / Scope Abstraction:** Traditional `lock` lowered to `Monitor.Enter` and a `try / finally { Monitor.Exit }` block, which was rigid and tied to monitor semantics.

## The C# 13 Way: `System.Threading.Lock`

In C# 13, you replace `object` with `System.Threading.Lock`:

```csharp
using System.Threading;

public class CacheManager
{
    private readonly Lock _gate = new();

    public void AddOrUpdate(string key, object item)
    {
        lock (_gate)
        {
            // Critical section
        }
    }
}
```

Notice the syntax inside the method didn't change: `lock (_gate)` is still valid!

However, the C# compiler treats `System.Threading.Lock` as a special type. Instead of emitting `Monitor.Enter(_gate)`, the compiler lowers that block to:

```csharp
using (_gate.EnterScope())
{
    // Critical section
}
```

### Why `EnterScope()` is Fast

`_gate.EnterScope()` returns a `Lock.Scope`, which is defined as a `ref struct`:

```csharp
public ref struct Scope
{
    public void Dispose();
}
```

Because `Scope` is a `ref struct`:
* It can **never escape to the managed heap**.
* It **cannot be boxed**.
* When the scope ends, `Dispose()` is invoked without interface dispatch or virtual method calls.
* On modern operating systems (like Linux futexes or Windows SRW locks), the underlying implementation uses highly optimized, cache-aligned synchronization primitives rather than CLR sync-block inflation.

If you don't want to use the `lock` keyword, you can use `using` directly:

```csharp
using (_gate.EnterScope())
{
    DoWork();
}
```

## Bonus: How `params ReadOnlySpan<T>` Kills Heap Allocations

While we're talking about C# 13 performance improvements, there is another feature that quietly eliminates hidden heap allocations in hot paths: **`params Collections`**.

Ever since C# 1.0, the `params` keyword required an array:

```csharp
public void LogMetrics(string tag, params int[] values)
```

Every single time a caller wrote:

```csharp
LogMetrics("latency", 12, 45, 89);
```

The C# compiler quietly generated:

```csharp
LogMetrics("latency", new int[] { 12, 45, 89 }); // 💥 Heap allocation!
```

If that method ran inside a high-throughput loop (e.g. logging, string concatenation, or parsing), you generated massive garbage collection pressure just passing arguments.

### C# 13 Fixes This

In C# 13, `params` works with **any collection type**, including `ReadOnlySpan<T>`:

```csharp
public void LogMetrics(string tag, params ReadOnlySpan<int> values)
{
    for (int i = 0; i < values.Length; i++)
    {
        Process(values[i]);
    }
}
```

Now, when you call:

```csharp
LogMetrics("latency", 12, 45, 89);
```

The compiler creates a buffer on the **stack** (using `stackalloc` semantics under the hood) and passes a `ReadOnlySpan<int>`.

**Heap allocations: 0 bytes. GC pressure: zero.**

And for callers, the syntax is 100% identical.

## Summary

* Run the **IDE0330** refactoring across your .NET 9 solutions to replace `private readonly object _lock = new();` with `private readonly Lock _lock = new();`.
* Update utility methods taking `params T[]` to `params ReadOnlySpan<T>` where possible to eliminate call-site heap allocations.
