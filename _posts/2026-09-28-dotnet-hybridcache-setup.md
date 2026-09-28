---
tags: ["dotnet", "csharp", "redis", "performance"]
categories: ["dotnet", "architecture"]
title: ".NET HybridCache Setup: The Multi-Pod Stampede Trap"
image:
  path: /assets/img/2026-09-28/main.jpg
  alt: A split-level workshop with instant counter pickups while delivery vans queue bumper-to-bumper outside.
---

I love distributed caching. I also love when my SQL Server container does not spike to 100% CPU on a Monday morning because fifty parallel requests hit an expired key at 09:14:02.

For years, avoiding that spike in .NET meant writing eighty lines of fragile boilerplate. You glued an in-memory cache to a Redis instance, wrapped the call in a `SemaphoreSlim` dictionary to prevent a thundering herd, and prayed you never forgot to release a lock.

When .NET introduced `HybridCache`, it promised to erase all that plumbing with a single call to `GetOrCreateAsync()`. It combines fast in-memory storage (L1) with shared Redis storage (L2) and kills cache stampedes right out of the box.

I wired it up in a test project to see how it works under pressure. It is fast, clean, and solves a real headache - but if you run your service across multiple containers, there is one architectural trap you need to know before going to production.

## The Two-Tier Problem

In a typical web API, caching usually happens at two speeds:

1. **L1 (In-Memory Cache):** Lives inside your application process memory via `IMemoryCache`. Reading it takes microseconds directly off your heap with zero network delay or serialization, but memory disappears on restart and is never shared across servers.
2. **L2 (Distributed Cache):** Lives in an external store like Redis. Reading it takes a few milliseconds over the network. Every server instance shares the same data, and the cache survives application deployments.

In an ideal world, you want both. You check fast L1 first, then fall back to L2 on a miss. If both miss, you query your database, save the result to L2, and keep a copy in L1 for next time.

The nasty part is the **cache stampede** (also known as the thundering herd).

Imagine a popular product page that gets fifty requests every second when the cache suddenly expires. All fifty incoming requests see a cache miss at the exact same millisecond. Instead of one request refreshing the cache, all fifty fire off identical database queries simultaneously.

Your database CPU spikes, connections queue up, and response times tank.

`HybridCache` stops this by **coalescing requests**. When fifty requests ask for the same missing key at the same time, `HybridCache` lets only the first request run the database query. The other forty-nine requests wait patiently in memory and share the single result when it arrives.

## Spinning Up Redis in Podman

To test this locally, we need a running Redis instance for our L2 tier. I spun up an Alpine container in rootless Podman:

```bash
podman run -d --name redis-dev -p 6379:6379 redis:alpine
```

```text
7c2e391b4fa1807d9f67a21db33385ee0b471ec5aa263884144e59f2390fca51
```

A quick check with `podman ps` confirms Redis is listening on port `6379`:

```bash
podman ps --filter "name=redis-dev"
```

```text
CONTAINER ID  IMAGE                        COMMAND         CREATED        STATUS        PORTS                   NAMES
7c2e391b4fa1  docker.io/library/redis:alpine  redis-server    2 seconds ago  Up 2 seconds  0.0.0.0:6379->6379/tcp  redis-dev
```

## Adding the Packages

Create a fresh ASP.NET Core Web API or console project, then install two packages:

```bash
dotnet add package Microsoft.Extensions.Caching.Hybrid
dotnet add package Microsoft.Extensions.Caching.StackExchangeRedis
```

```text
Determining projects to restore...
Writing /tmp/tmpY8xKl1/obj/project.assets.json
Restored /home/eich/Projects/HybridCacheDemo/HybridCacheDemo.csproj (in 412 ms).
```

- `Microsoft.Extensions.Caching.Hybrid` provides the core `HybridCache` coordinator and the in-memory L1 engine.
- `Microsoft.Extensions.Caching.StackExchangeRedis` registers the `IDistributedCache` implementation that `HybridCache` uses for L2.

## Wiring HybridCache in Program.cs

Open `Program.cs`. Registering both tiers takes only a few lines:

```csharp
var builder = WebApplication.CreateBuilder(args);

// 1. Register L2: Redis Distributed Cache
builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = "localhost:6379";
    options.InstanceName = "catalog_";
});

// 2. Register HybridCache
builder.Services.AddHybridCache(options =>
{
    options.MaximumKeyLength = 512;
    options.MaximumPayloadBytes = 1024 * 1024; // 1 MB limit

    // Global default expiration policies
    options.DefaultEntryOptions = new HybridCacheEntryOptions
    {
        Expiration = TimeSpan.FromHours(1),            // Total L2 TTL (Redis)
        LocalCacheExpiration = TimeSpan.FromMinutes(2) // L1 TTL (In-Memory)
    };
});

var app = builder.Build();
```

Notice the two expiration knobs inside `HybridCacheEntryOptions`:

- `LocalCacheExpiration`: How long the item stays inside the fast in-memory L1 cache (2 minutes).
- `Expiration`: How long the item lives in shared Redis storage (1 hour).

Keeping `LocalCacheExpiration` shorter than total `Expiration` keeps your process memory lean while letting Redis absorb lookups for the rest of the hour.

## Fetching Data with GetOrCreateAsync

Here is a simple catalog service demonstrating how to read, cache, and tag items:

```csharp
using Microsoft.Extensions.Caching.Hybrid;

namespace HybridCacheDemo;

public record ProductDto(int Id, string Sku, string Name, decimal Price);

public class CatalogService(HybridCache cache, ILogger<CatalogService> logger)
{
    public async ValueTask<ProductDto> GetProductAsync(int id, CancellationToken ct = default)
    {
        string cacheKey = $"product:{id}";
        string[] tags = [$"product:{id}", "products"];

        return await cache.GetOrCreateAsync(
            key: cacheKey,
            state: (id, logger),
            factory: static async (state, token) =>
            {
                var (productId, log) = state;
                log.LogInformation("Cache miss! Querying database for product {Id}...", productId);

                // Simulate an expensive 200ms database query
                await Task.Delay(200, token);

                return new ProductDto(productId, $"SKU-{productId}", "Mechanical Keyboard", 129.99m);
            },
            tags: tags,
            cancellationToken: ct
        );
    }
}
```

Notice the `state` parameter passed into `GetOrCreateAsync`.

By passing our dependencies as a state tuple into a `static` lambda, the C# compiler never has to allocate a hidden class on the heap just to capture variables. `HybridCache` was built for high-throughput paths, and small tricks like this keep Garbage Collection (GC) pauses near zero.

## Putting Stampede Protection to the Test

To verify that request coalescing actually works, I fired 100 concurrent tasks at the exact same product ID while the cache was cold:

```csharp
var tasks = Enumerable.Range(1, 100)
    .Select(_ => catalogService.GetProductAsync(42).AsTask())
    .ToArray();

await Task.WhenAll(tasks);
```

If we ran this with traditional caching, our console would show 100 log lines and our database would take 100 hits.

Here is what `HybridCache` printed:

```text
info: HybridCacheDemo.CatalogService[0]
      Cache miss! Querying database for product 42...
```

One log entry.

Ninety-nine requests saw that an operation for key `product:42` was already running, attached themselves to the in-flight task, and received the value as soon as the factory completed.

## The Multi-Pod Trap

This request coalescing is fantastic. But here is the trap: **HybridCache coalesces requests in-process only.**

Under the hood, `HybridCache` uses an internal `ConcurrentDictionary` to track in-flight requests. That dictionary lives inside the memory of a single running CLR process. It does not use distributed locks in Redis.

Why does this matter?

Imagine your application runs in Kubernetes with 10 pods behind a load balancer:

1. Key `product:42` expires in Redis.
2. A traffic wave hits your cluster with 1,000 concurrent requests, spread across all 10 pods (100 requests per pod).
3. Pod 1 sees a miss and coalesces its 100 requests into **1** database query.
4. Pod 2 also sees a miss and coalesces its 100 requests into **1** database query.
5. Every single pod from Pod 1 to Pod 10 does the exact same thing.

Instead of 1 database query, your database gets **10 simultaneous queries**.

Going from 1,000 queries down to 10 is still a 99% reduction in traffic, which is a huge win for most systems. But if you have 50 pods running during peak hours, an expired hot key will still send a burst of 50 simultaneous queries to your database.

### The L1 Staleness Window

There is a second subtlety with multiple pods: cache eviction.

When Pod 1 calls `await cache.RemoveAsync("product:42")`, it removes the item from its own L1 memory and deletes the key from Redis.

However, Pods 2 through 10 have no idea that Pod 1 changed anything. Because `HybridCache` does not include an automatic pub/sub backplane (a message channel where pods broadcast "hey, I invalidated key X, evict it from your RAM!") out of the box, Pods 2 through 10 will keep returning their local copy from L1 memory until their `LocalCacheExpiration` timer runs out.

If your system cannot tolerate that brief window of drift across pods:

- Keep `LocalCacheExpiration` short (e.g. 30 to 60 seconds).
- Set `HybridCacheEntryFlags.DisableLocalCache` for volatile entities that must always read from Redis.
- Or use a library like FusionCache if you require an integrated pub/sub invalidation backplane across all instances.

## Tag-Based Invalidation

One of the cleanest features in `HybridCache` is invalidation by tag.

In classic Redis setups, clearing all products in a category meant running expensive `KEYS` or `SCAN` commands over millions of entries, or maintaining manual Redis sets of keys.

`HybridCache` uses **logical timestamps** instead:

```csharp
// Invalidate every entry tagged with "products"
await cache.RemoveByTagAsync("products");
```

When you call `RemoveByTagAsync("products")`, `HybridCache` does not delete every matching product key. Instead, it writes a single timestamp record into Redis: `tag:products -> [CurrentTimestamp]`.

The next time any request looks up `product:42`, `HybridCache` compares the entry creation time with the tag invalidation timestamp. If the tag is newer, `HybridCache` considers the entry expired on the spot, runs the factory, and updates the cache.

This turns an expensive $O(N)$ deletion into a lightweight $O(1)$ timestamp check.

## Summary

- **Combines L1 and L2:** `HybridCache` bridges fast in-memory objects and shared Redis storage behind a single `GetOrCreateAsync()` API.
- **In-process stampede protection:** Concurrent requests on the same instance coalesce into a single factory call, protecting your database from sudden spikes.
- **The multi-pod trap:** Coalescing is per-instance, not distributed. If you run 10 pods, an expired key can trigger 10 simultaneous database queries across the cluster.
- **Mind the staleness window:** In multi-node deployments, nodes do not immediately know when another node calls `RemoveAsync()`. Keep `LocalCacheExpiration` conservative.
- **Fast tag invalidation:** `RemoveByTagAsync()` uses $O(1)$ timestamp checks instead of slow Redis key scans.

If you have been writing hand-rolled caching helpers with `IMemoryCache` and `IDistributedCache`, switch to `HybridCache`. It is faster, safer, and deletes dozens of lines of delicate locking code. Just remember to size your database connections for the number of running pods, not just one.

## Resources

- [Microsoft Learn: HybridCache Library in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/performance/caching/hybrid) - Official documentation covering architecture, setup, and serialization options.
- [GitHub: DefaultHybridCache.cs Source Code](https://github.com/dotnet/extensions/blob/a4a3d809e9ed0d842a000f542e539fb89b517416/src/Libraries/Microsoft.Extensions.Caching.Hybrid/Internal/DefaultHybridCache.cs#L1) - The core engine implementation showing key validation and L1/L2 orchestration.
- [GitHub: StampedeStateT.cs Source Code](https://github.com/dotnet/extensions/blob/a4a3d809e9ed0d842a000f542e539fb89b517416/src/Libraries/Microsoft.Extensions.Caching.Hybrid/Internal/DefaultHybridCache.StampedeStateT.cs#L14) - The internal request coalescing and task joining implementation.
- [GitHub: HybridCacheEntryOptions.cs Source Code](https://github.com/dotnet/runtime/blob/e5fc9669cc6a67694d46987c753cc13d995b2623/src/libraries/Microsoft.Extensions.Caching.Abstractions/src/Hybrid/HybridCacheEntryOptions.cs#L20) - Configuration source defining `Expiration`, `LocalCacheExpiration`, and entry flags.
- [GitHub: IHybridCacheSerializer.cs Source Code](https://github.com/dotnet/runtime/blob/e5fc9669cc6a67694d46987c753cc13d995b2623/src/libraries/Microsoft.Extensions.Caching.Abstractions/src/Hybrid/IHybridCacheSerializer.cs#L13) - The zero-allocation serialization contract using `ReadOnlySequence<byte>` and `IBufferWriter<byte>`.
- [StackExchange.Redis Documentation](https://stackexchange.github.io/StackExchange.Redis/) - Reference for configuring Redis connections and cluster settings in .NET.
