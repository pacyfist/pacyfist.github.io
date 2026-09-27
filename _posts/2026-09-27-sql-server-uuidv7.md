---
tags: ["sqlserver", "dotnet", "csharp", "performance"]
categories: ["sqlserver", "dotnet"]
title: "SQL Server UUIDv7: Why Guid.CreateVersion7 Still Fragments"
image:
  path: /assets/img/2026-09-27/main.jpg
  alt: An antique clockwork filing cabinet that insists on sorting index cards from back to front.
---

Back in February 2025, I wrote about [taming the UUID beast](/posts/taming-the-uuid-beast-how-to-avoid-clustered-index-fragmentation-in-sql-server/) and showed how `NEWSEQUENTIALID()` kept 1,000,000 clustered index rows under 1% fragmentation. But it always came with an annoying catch: SQL Server held the keys, and your C# application had to wait for a database roundtrip just to learn a new entity's ID.

When .NET 9 introduced RFC 9562 support with `Guid.CreateVersion7()`, it felt like the holy grail. We could finally generate time-ordered, globally unique identifiers right inside our application code, assign foreign keys in memory, and keep our clustered indexes nice and tidy. Naturally, I fired up a fresh test suite to celebrate.

Then I checked `sys.dm_db_index_physical_stats`, and my jaw hit the keyboard: **99.04% index fragmentation**.

## The Dream of Client-Side GUIDs

Generating primary keys on the client solves real architectural headaches. You can build entire aggregate graphs in memory, assign parent and child identifiers before saving, and stream events to Kafka without waiting for SQL Server to hand back identity values.

Traditional GUIDs generated with `Guid.NewGuid()` (`NEWID()` in T-SQL) destroy database performance. Because their bits are completely random, every new insert lands in a random spot in your clustered index B-tree. That randomness forces 50/50 mid-page splits, leaves your data pages half empty, and blows up storage size.

UUIDv7 was designed specifically to fix this problem across the entire industry. RFC 9562 packs a 48-bit Unix millisecond timestamp into the leading bytes. In PostgreSQL, SQLite, or MySQL, UUIDv7 inserts sort strictly in chronological order, producing clean append-only B-trees with virtually zero fragmentation.

So why does standard .NET `Guid.CreateVersion7()` completely ruin a SQL Server clustered index?

## Spinning Up the Benchmark in Podman

To find out, I put together an isolated benchmark using rootless Podman on Linux, spinning up both SQL Server 2022 and the latest SQL Server 2025 release side by side:

```bash
# SQL Server 2022
podman run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=BenchmarkSql2026!" -p 1433:1433 -d --name sql2022 mcr.microsoft.com/mssql/server:2022-latest
```

```text
19b0ce730b40638355a5ef87181cf08b62332f27b0b607dba9adbfecfb6e3b26
```

```bash
# SQL Server 2025 (latest release)
podman run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=BenchmarkSql2026!" -p 1434:1433 -d --name sql2025 mcr.microsoft.com/mssql/server:2025-latest
```

```text
939d9dbda993d1ab3f8dccd54dc161ccdddb2d5baef5873a66e92170d3e6b89b
```

I wrote a .NET 10 benchmark harness that creates a dedicated database (`BenchmarkDb`) on each instance and tests five distinct identifier strategies:

1. **Random Guid (`Guid.NewGuid` / `NEWID`)**
2. **SQL Server `NEWSEQUENTIALID()`** (database default constraint)
3. **Unmodified .NET `Guid.CreateVersion7()`**
4. **Byte-Swapped UUIDv7** (mapped from standard `Guid.CreateVersion7`)
5. **Byte-Swapped Monotonic UUIDv7** (with RFC 9562 sub-millisecond counter)

Each table used an identical clustered primary key schema with a payload column and timestamp:

```sql
CREATE TABLE [dbo].[Bench_RandomGuid] (
    [Id] UNIQUEIDENTIFIER NOT NULL,
    [SequenceNumber] INT NOT NULL,
    [Payload] NVARCHAR(100) NOT NULL,
    [CreatedAt] DATETIME2(7) NOT NULL,
    CONSTRAINT [PK_Bench_RandomGuid] PRIMARY KEY CLUSTERED ([Id] ASC)
);
```

The runner inserted 200,000 rows per strategy (1,000,000 rows total) inside single transactions using batched multi-row inserts of 1,000 rows:

```csharp
private static async Task RunStrategyAsync(
    string tableName,
    Func<Guid> guidGenerator,
    bool useDbDefault)
{
    await using var conn = new SqlConnection(DbConnString);
    await conn.OpenAsync();

    int batches = TotalRows / BatchSize; // 200,000 / 1,000

    await using var tx = conn.BeginTransaction();
    var sb = new StringBuilder(128 * BatchSize);

    for (int b = 0; b < batches; b++)
    {
        sb.Clear();
        if (useDbDefault)
        {
            sb.Append($"INSERT INTO [dbo].[{tableName}] ([SequenceNumber], [Payload], [CreatedAt]) VALUES ");
            for (int i = 0; i < BatchSize; i++)
            {
                int seq = (b * BatchSize) + i;
                if (i > 0) sb.Append(", ");
                sb.Append($"({seq}, 'Payload-{seq:D7}', SYSUTCDATETIME())");
            }
        }
        else
        {
            sb.Append($"INSERT INTO [dbo].[{tableName}] ([Id], [SequenceNumber], [Payload], [CreatedAt]) VALUES ");
            for (int i = 0; i < BatchSize; i++)
            {
                int seq = (b * BatchSize) + i;
                Guid id = guidGenerator();
                if (i > 0) sb.Append(", ");
                sb.Append($"('{id}', {seq}, 'Payload-{seq:D7}', SYSUTCDATETIME())");
            }
        }

        await using var cmd = new SqlCommand(sb.ToString(), conn, tx);
        await cmd.ExecuteNonQueryAsync();
    }

    await tx.CommitAsync();
}
```

We execute this loop across each strategy:

```csharp
// 1. Random Guid
await RunStrategyAsync("Bench_RandomGuid", () => Guid.NewGuid(), useDbDefault: false);

// 2. SQL Server NEWSEQUENTIALID() (database default)
await RunStrategyAsync("Bench_SequentialGuid", () => Guid.Empty, useDbDefault: true);

// 3. Unmodified .NET Guid.CreateVersion7()
await RunStrategyAsync("Bench_UuidV7_Unmodified", () => Guid.CreateVersion7(), useDbDefault: false);

// 4. Byte-Swapped UUIDv7 (from Guid.CreateVersion7)
await RunStrategyAsync("Bench_UuidV7_ByteSwapped", () => SqlUuidV7.ToSqlGuid(Guid.CreateVersion7()), useDbDefault: false);

// 5. Monotonic Byte-Swapped UUIDv7 (RFC 9562 sub-ms counter)
await RunStrategyAsync("Bench_UuidV7_Monotonic", () => MonotonicSqlUuidV7.Create(), useDbDefault: false);
```

We run the suite first against SQL Server 2022 on port 1433:

```bash
dotnet run -c Release -- 1433
```

```text
==========================================================================================================
                         SQL SERVER 2022 UUIDv7 BENCHMARK SUITE
                         Rows Per Strategy: 200,000 | Batch Size: 1,000
==========================================================================================================

Connecting to SQL Server
[SUCCESS] Connected to SQL Server!
SQL Server Version: Microsoft SQL Server 2022 (RTM-CU27) (KB5104824) - 16.0.4295.3 (X64)  	Aug 26 2026 11:02:22  	Copyright (C) 2022 Microsoft Corporation 	Developer Edition (64-bit) on Linux (Ubuntu 22.04.5 LTS) <X64>
Rebuilding clean BenchmarkDb database and tables...
Database BenchmarkDb initialized with all 5 benchmark tables.

[1/5] Running Strategy 1: Random Guid (Guid.NewGuid)...
  Inserted 200,000 rows in 31,140 ms (6,423 rows/sec). Page Splits Delta: 2,540
  Analyzing index physical stats (DETAILED mode)...
  Fragmentation: 99.21% | Pages: 2,519 | Fragments: 2,519 | Page Density: 69.62%

[2/5] Running Strategy 2: SQL Server NEWSEQUENTIALID()...
  Inserted 200,000 rows in 23,746 ms (8,422 rows/sec). Page Splits Delta: 1,767
  Analyzing index physical stats (DETAILED mode)...
  Fragmentation: 0.74% | Pages: 1,755 | Fragments: 15 | Page Density: 99.94%

[3/5] Running Strategy 3: Unmodified .NET Guid.CreateVersion7()...
  Inserted 200,000 rows in 31,470 ms (6,355 rows/sec). Page Splits Delta: 2,506
  Analyzing index physical stats (DETAILED mode)...
  Fragmentation: 99.04% | Pages: 2,493 | Fragments: 2,493 | Page Density: 70.35%

[4/5] Running Strategy 4: Byte-swapped SqlGuid UUIDv7 (Guid.CreateVersion7)...
  Inserted 200,000 rows in 30,455 ms (6,567 rows/sec). Page Splits Delta: 2,701
  Analyzing index physical stats (DETAILED mode)...
  Fragmentation: 83.90% | Pages: 2,683 | Fragments: 2,253 | Page Density: 65.36%

[5/5] Running Strategy 5: Byte-swapped Monotonic UUIDv7 (RFC 9562 Sub-ms Counter)...
  Inserted 200,000 rows in 30,288 ms (6,603 rows/sec). Page Splits Delta: 1,767
  Analyzing index physical stats (DETAILED mode)...
  Fragmentation: 0.74% | Pages: 1,755 | Fragments: 15 | Page Density: 99.94%

==========================================================================================================
                                     FINAL BENCHMARK RESULTS SUMMARY
==========================================================================================================
Strategy                                                | Duration   | Rows/Sec   | Fragmentation  | Pages   | Density 
--------------------------------------------------------------------------------------------------------------------
Strategy 1: Random Guid (Guid.NewGuid)                  |  31,140 ms |    6,423 |       99.21% |   2,519 |  69.62%
Strategy 2: SQL Server NEWSEQUENTIALID()                |  23,746 ms |    8,422 |        0.74% |   1,755 |  99.94%
Strategy 3: Unmodified .NET Guid.CreateVersion7()       |  31,470 ms |    6,355 |       99.04% |   2,493 |  70.35%
Strategy 4: Byte-swapped UUIDv7 (Guid.CreateVersion7)   |  30,455 ms |    6,567 |       83.90% |   2,683 |  65.36%
Strategy 5: Byte-swapped Monotonic UUIDv7 (Sub-ms Counter) |  30,288 ms |    6,603 |        0.74% |   1,755 |  99.94%
==========================================================================================================
```

Then we run the identical benchmark suite against the latest SQL Server 2025 release on port 1434:

```bash
dotnet run -c Release -- 1434
```

```text
==========================================================================================================
                         SQL SERVER 2025 UUIDv7 BENCHMARK SUITE
                         Rows Per Strategy: 200,000 | Batch Size: 1,000
==========================================================================================================

Connecting to SQL Server
[SUCCESS] Connected to SQL Server!
SQL Server Version: Microsoft SQL Server 2025 (RTM-CU9) (KB5122048) - 17.0.5005.3 (X64)  	Aug 27 2026 09:30:16  	Copyright (C) 2025 Microsoft Corporation 	Enterprise Developer Edition (64-bit) on Linux (Ubuntu 24.04.4 LTS) <X64>
Rebuilding clean BenchmarkDb database and tables...
Database BenchmarkDb initialized with all 5 benchmark tables.

[1/5] Running Strategy 1: Random Guid (Guid.NewGuid)...
  Inserted 200,000 rows in 42,578 ms (4,697 rows/sec). Page Splits Delta: 2,553
  Analyzing index physical stats (DETAILED mode)...
  Fragmentation: 99.21% | Pages: 2,530 | Fragments: 2,530 | Page Density: 69.32%

[2/5] Running Strategy 2: SQL Server NEWSEQUENTIALID()...
  Inserted 200,000 rows in 28,996 ms (6,898 rows/sec). Page Splits Delta: 1,767
  Analyzing index physical stats (DETAILED mode)...
  Fragmentation: 0.74% | Pages: 1,755 | Fragments: 15 | Page Density: 99.94%

[3/5] Running Strategy 3: Unmodified .NET Guid.CreateVersion7()...
  Inserted 200,000 rows in 40,089 ms (4,989 rows/sec). Page Splits Delta: 2,527
  Analyzing index physical stats (DETAILED mode)...
  Fragmentation: 98.93% | Pages: 2,515 | Fragments: 2,515 | Page Density: 69.73%

[4/5] Running Strategy 4: Byte-swapped SqlGuid UUIDv7 (Guid.CreateVersion7)...
  Inserted 200,000 rows in 38,770 ms (5,159 rows/sec). Page Splits Delta: 2,734
  Analyzing index physical stats (DETAILED mode)...
  Fragmentation: 82.80% | Pages: 2,715 | Fragments: 2,251 | Page Density: 64.59%

[5/5] Running Strategy 5: Byte-swapped Monotonic UUIDv7 (RFC 9562 Sub-ms Counter)...
  Inserted 200,000 rows in 38,465 ms (5,200 rows/sec). Page Splits Delta: 1,767
  Analyzing index physical stats (DETAILED mode)...
  Fragmentation: 0.74% | Pages: 1,755 | Fragments: 15 | Page Density: 99.94%

==========================================================================================================
                                     FINAL BENCHMARK RESULTS SUMMARY
==========================================================================================================
Strategy                                                | Duration   | Rows/Sec   | Fragmentation  | Pages   | Density 
--------------------------------------------------------------------------------------------------------------------
Strategy 1: Random Guid (Guid.NewGuid)                  |  42,578 ms |    4,697 |       99.21% |   2,530 |  69.32%
Strategy 2: SQL Server NEWSEQUENTIALID()                |  28,996 ms |    6,898 |        0.74% |   1,755 |  99.94%
Strategy 3: Unmodified .NET Guid.CreateVersion7()       |  40,089 ms |    4,989 |       98.93% |   2,515 |  69.73%
Strategy 4: Byte-swapped UUIDv7 (Guid.CreateVersion7)   |  38,770 ms |    5,159 |       82.80% |   2,715 |  64.59%
Strategy 5: Byte-swapped Monotonic UUIDv7 (Sub-ms Counter) |  38,465 ms |    5,200 |        0.74% |   1,755 |  99.94%
==========================================================================================================
```

## The DMV Scoreboard: Side-by-Side Comparison

Let's look at the numbers pulled straight from `sys.dm_db_index_physical_stats` and `sys.dm_os_performance_counters` across both database versions:

| Strategy | Metric | SQL Server 2022 (CU27) | SQL Server 2025 (CU9) |
| :--- | :--- | :---: | :---: |
| **Strategy 1: Random Guid (`Guid.NewGuid`)** | Leaf Fragmentation | **99.21%** | **99.21%** |
| | Leaf Pages | 2,519 | 2,530 |
| | Page Density | 69.62% | 69.32% |
| | Page Splits Delta | 2,540 | 2,553 |
| **Strategy 2: SQL Server `NEWSEQUENTIALID()`** | Leaf Fragmentation | **0.74%** | **0.74%** |
| | Leaf Pages | **1,755** | **1,755** |
| | Page Density | **99.94%** | **99.94%** |
| | Page Splits Delta | 1,767 | 1,767 |
| **Strategy 3: Unmodified `Guid.CreateVersion7()`** | Leaf Fragmentation | **99.04%** | **98.93%** |
| | Leaf Pages | 2,493 | 2,515 |
| | Page Density | 70.35% | 69.73% |
| | Page Splits Delta | 2,506 | 2,527 |
| **Strategy 4: Byte-Swapped UUIDv7** | Leaf Fragmentation | **83.90%** | **82.80%** |
| | Leaf Pages | 2,683 | 2,715 |
| | Page Density | 65.36% | 64.59% |
| | Page Splits Delta | 2,701 | 2,734 |
| **Strategy 5: Monotonic Byte-Swapped UUIDv7** | Leaf Fragmentation | **0.74%** | **0.74%** |
| | Leaf Pages | **1,755** | **1,755** |
| | Page Density | **99.94%** | **99.94%** |
| | Page Splits Delta | 1,767 | 1,767 |

Look closely at Strategy 3 across both engines. Unmodified `Guid.CreateVersion7()` is **indistinguishable from random `Guid.NewGuid()`** on both SQL Server 2022 and the latest SQL Server 2025.

Both suffered over 98.9% - 99.2% fragmentation. Both needed more than 2,500 leaf pages to store the exact same 200,000 rows that `NEWSEQUENTIALID()` stored in 1,755 pages. That is **43.5% storage bloating** in your data file and 43.5% wasted memory in your SQL Server buffer pool cache!

Why does an official time-ordered GUID standard fail so spectacularly across both generations of SQL Server?

## Mystery 1: The 1998 Time Capsule

Most modern database engines compare bytes left to right, from index 0 to index 15. If your timestamp sits in bytes 0 to 5, the database naturally sorts your rows chronologically.

SQL Server does not work that way. Its `uniqueidentifier` type dates back to SQL Server 7.0 in 1998, when UUIDv1 was the only game in town.

In UUIDv1, bytes 10 to 15 held the network card MAC address (`node`), bytes 8 and 9 held the clock sequence, and bytes 0 to 7 held the timestamp. Microsoft wanted rows generated by the same physical server to cluster together in the B-tree.

Because of that legacy decision, SQL Server sorts GUIDs by inspecting five distinct byte groups in this exact order:

```text
Order = [10, 11, 12, 13, 14, 15,  8, 9,  6, 7,  4, 5,  0, 1, 2, 3]
```

You can confirm this directly in the open-source .NET runtime repository inside `SqlGuid.cs`:

```csharp
// From dotnet/runtime: System.Data.Common/src/System/Data/SqlTypes/SqlGuid.cs
private static readonly int[] s_rgiGuidOrder = new int[16]
{
    10, 11, 12, 13, 14, 15,
    8, 9,
    6, 7,
    4, 5,
    0, 1, 2, 3
};
```

Now look at what RFC 9562 puts inside a standard UUIDv7:

- **Bytes 0 to 5 (48 bits):** Unix millisecond timestamp.
- **Bytes 6 and 7 (16 bits):** Version 7 and sub-millisecond counter/random bits.
- **Bytes 8 and 9 (16 bits):** Variant and random bits.
- **Bytes 10 to 15 (48 bits):** **Pure pseudorandom noise**.

When SQL Server compares two `uniqueidentifier` values, it **starts at bytes 10 to 15**. It treats 48 bits of pure random noise as the primary sorting key!

The chance of two rows having matching bytes 10 to 15 is 1 in 281 trillion. SQL Server **never even reaches bytes 0 to 5**. To the storage engine, your time-ordered UUIDv7 looks like pure chaos.

Even in the latest SQL Server 2025 release, Microsoft kept this legacy sorting behavior intact. Changing how `uniqueidentifier` values sort would silently break existing clustered indexes, partition schemes, and replication topologies across millions of databases worldwide.

## Mystery 2: Why Naive Byte Swapping Still Hits 83% Fragmentation

Once you realize SQL Server looks at bytes 10 to 15 first, the immediate reaction is simple: just move the 48-bit timestamp from bytes 0-5 over to bytes 10-15!

That is exactly what Strategy 4 did. But as the scoreboard shows, it still ended up with **82.80% - 83.90% fragmentation** and over **2,700 page splits** on both engines.

Why did simple byte swapping fail?

One millisecond is an eternity for modern CPUs. A high-throughput ingest pipeline or batch insert can easily generate thousands of GUIDs in a single millisecond.

The standard .NET `Guid.CreateVersion7()` implementation fills its secondary field (`rand_a`) with random entropy. When you generate 500 rows inside the same millisecond:

1. All 500 rows share the exact same timestamp in bytes 10 to 15.
2. SQL Server moves to its secondary comparison group (bytes 8 and 9).
3. Because those bytes contain random noise, rows within that millisecond insert out of order.

Those out-of-order inserts trigger localized 50/50 mid-page splits right inside your active leaf pages. You avoid total disaster across minutes, but high-throughput batches still fracture the index.

## The Real Fix: Monotonic Byte-Swapped UUIDv7

To achieve genuine sequentiality in SQL Server, we must combine two techniques:

1. **Byte-swap the 48-bit timestamp** so it lands in SQL Server's primary comparison slot (bytes 10 to 15).
2. **Implement RFC 9562 Section 6.2** by embedding a 12-bit monotonic sequence counter into bytes 6 and 7, which maps into SQL Server's secondary slot (bytes 8 and 9).

Across different milliseconds, the primary timestamp advances cleanly. Within the same millisecond, the 12-bit counter increments from 0 to 4,095 for every generated key.

SQL Server comparison inversions drop to zero. Every new row appends neatly to the end of the clustered index.

Look back at Strategy 5 in our scoreboard across both SQL Server 2022 and SQL Server 2025:
- **0.74% leaf fragmentation**
- **99.94% page density**
- **1,755 leaf pages**

It matched `NEWSEQUENTIALID()` down to the exact page count (1,755 pages) and identical split count (1,767 splits), but every single ID was generated in .NET memory before touching the database!

## The Complete Zero-Allocation C# Implementation

Here is the complete, high-performance C# generator. It uses `stackalloc` and `Span<byte>` so it never allocates a single byte on the managed heap:

```csharp
using System;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;

namespace MyProject.Data;

/// <summary>
/// Generates sequential UUIDv7 values optimized for SQL Server uniqueidentifier clustered indexes.
/// Implements RFC 9562 Section 6.2 with an atomic 12-bit sub-millisecond sequence counter.
/// </summary>
public static class MonotonicSqlUuidV7
{
    private static long _lastTimestampMs;
    private static ushort _sequence;
    private static readonly object _lock = new();

    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    public static Guid Create()
    {
        Span<byte> rfc = stackalloc byte[16];
        
        // Fill lower 64 bits with cryptographic entropy
        RandomNumberGenerator.Fill(rfc.Slice(8, 8));

        long now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        ushort seq;

        lock (_lock)
        {
            if (now > _lastTimestampMs)
            {
                _lastTimestampMs = now;
                _sequence = 0;
            }
            else
            {
                _sequence++;
                now = _lastTimestampMs;
            }
            seq = _sequence;
        }

        // Timestamp (48 bits, big-endian) in RFC slots 0..5
        rfc[0] = (byte)(now >> 40);
        rfc[1] = (byte)(now >> 32);
        rfc[2] = (byte)(now >> 24);
        rfc[3] = (byte)(now >> 16);
        rfc[4] = (byte)(now >> 8);
        rfc[5] = (byte)now;

        // RFC slots 6..7: Version (0x7) + 12-bit Monotonic Sequence Counter
        rfc[6] = (byte)(0x70 | ((seq >> 8) & 0x0F));
        rfc[7] = (byte)(seq & 0xFF);

        // RFC slot 8: Variant (0b10)
        rfc[8] = (byte)((rfc[8] & 0x3F) | 0x80);

        // Map RFC bytes into SQL Server uniqueidentifier precedence order
        Span<byte> sql = stackalloc byte[16];

        // SQL Group 1 (Highest): Indices 10..15 <- 48-bit Unix Timestamp
        sql[10] = rfc[0];
        sql[11] = rfc[1];
        sql[12] = rfc[2];
        sql[13] = rfc[3];
        sql[14] = rfc[4];
        sql[15] = rfc[5];

        // SQL Group 2: Indices 8..9 <- Version 7 + 12-bit Counter
        sql[8] = rfc[6];
        sql[9] = rfc[7];

        // SQL Group 3: Indices 6..7 <- Variant + Entropy High
        sql[6] = rfc[8];
        sql[7] = rfc[9];

        // SQL Group 4: Indices 4..5 <- Entropy Mid
        sql[4] = rfc[10];
        sql[5] = rfc[11];

        // SQL Group 5 (Lowest): Indices 0..3 <- Entropy Low
        sql[0] = rfc[12];
        sql[1] = rfc[13];
        sql[2] = rfc[14];
        sql[3] = rfc[15];

        return new Guid(sql);
    }

    /// <summary>
    /// Reverses the SQL Server byte mapping to restore standard RFC 9562 big-endian UUIDv7.
    /// Useful when publishing entities to external APIs, Kafka, or PostgreSQL.
    /// </summary>
    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    public static Guid ToRfcUuid7(Guid sqlGuid)
    {
        Span<byte> sql = stackalloc byte[16];
        sqlGuid.TryWriteBytes(sql);

        Span<byte> rfc = stackalloc byte[16];

        rfc[0] = sql[10];
        rfc[1] = sql[11];
        rfc[2] = sql[12];
        rfc[3] = sql[13];
        rfc[4] = sql[14];
        rfc[5] = sql[15];

        rfc[6] = sql[8];
        rfc[7] = sql[9];

        rfc[8] = sql[6];
        rfc[9] = sql[7];

        rfc[10] = sql[4];
        rfc[11] = sql[5];

        rfc[12] = sql[0];
        rfc[13] = sql[1];
        rfc[14] = sql[2];
        rfc[15] = sql[3];

        return new Guid(rfc, bigEndian: true);
    }
}
```

## Plugging It Into EF Core

Entity Framework Core lets you customize client-side value generation by subclassing `ValueGenerator<Guid>`:

```csharp
using System;
using Microsoft.EntityFrameworkCore.ChangeTracking;
using Microsoft.EntityFrameworkCore.ValueGeneration;

namespace MyProject.Data;

public sealed class SqlVersion7GuidValueGenerator : ValueGenerator<Guid>
{
    public override Guid Next(EntityEntry entry) => MonotonicSqlUuidV7.Create();

    public override bool GeneratesTemporaryValues => false;
}
```

You can register this generator for all Guid primary keys across your entire application inside `OnModelCreating`:

```csharp
public class AppDbContext : DbContext
{
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // Automatically assign MonotonicSqlUuidV7 to all Guid primary keys
        foreach (var entityType in modelBuilder.Model.GetEntityTypes())
        {
            foreach (var property in entityType.GetProperties())
            {
                if (property.ClrType == typeof(Guid) && property.IsKey())
                {
                    property.SetValueGeneratorFactory((_, _) => new SqlVersion7GuidValueGenerator());
                }
            }
        }
    }
}
```

Whenever you call `new Order()` or `new OrderItem()`, EF Core populates the primary key immediately. You can wire up parent-child navigation properties in memory without awaiting database identity seeds.

## Inspecting Your Own Indexes

If you want to verify your existing tables, run this diagnostic query against your database. Setting the mode to `DETAILED` reports exact page space density alongside logical fragmentation:

```sql
SELECT 
    OBJECT_NAME(ips.object_id, ips.database_id) AS TableName,
    i.name AS IndexName,
    ips.index_type_desc AS IndexType,
    ips.page_count AS TotalPages,
    CAST(ips.page_count * 8.0 / 1024.0 AS DECIMAL(10, 2)) AS IndexSizeMB,
    CAST(ips.avg_fragmentation_in_percent AS DECIMAL(5, 2)) AS AvgFragmentationPct,
    CAST(ips.avg_page_space_used_in_percent AS DECIMAL(5, 2)) AS AvgPageSpaceUsedPct,
    ips.fragment_count AS FragmentCount,
    ips.record_count AS TotalRows
FROM sys.dm_db_index_physical_stats(
    DB_ID(), 
    OBJECT_ID(N'dbo.Orders'), 
    1, -- Clustered Index
    NULL, 
    'DETAILED'
) ips
INNER JOIN sys.indexes i 
    ON ips.object_id = i.object_id 
    AND ips.index_id = i.index_id
WHERE ips.index_level = 0; -- Leaf level only
```

*(Replace `dbo.Orders` with your target table name, or pass `NULL` to evaluate every table in your database.)*

Here is what the output looks like when comparing random GUIDs against our monotonic UUIDv7 keys across both database engines:

| TableName | IndexType | TotalPages | IndexSizeMB | AvgFragmentationPct | AvgPageSpaceUsedPct | FragmentCount | TotalRows |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Bench_RandomGuid (2022) | CLUSTERED INDEX | 2,519 | 19.68 MB | 99.21% | 69.62% | 2,519 | 200,000 |
| Bench_UuidV7_Monotonic (2022) | CLUSTERED INDEX | 1,755 | 13.71 MB | 0.74% | 99.94% | 15 | 200,000 |
| Bench_RandomGuid (2025) | CLUSTERED INDEX | 2,530 | 19.77 MB | 99.21% | 69.32% | 2,530 | 200,000 |
| Bench_UuidV7_Monotonic (2025) | CLUSTERED INDEX | 1,755 | 13.71 MB | 0.74% | 99.94% | 15 | 200,000 |

If your `AvgPageSpaceUsedPct` sits down around 65% to 70%, random GUID inserts are silently stealing a third of your storage and buffer pool memory.

## Summary

- **Standard `Guid.CreateVersion7()` fails on SQL Server 2022 and 2025**: Because SQL Server evaluates bytes 10 to 15 first, it treats UUIDv7 as random noise, hitting **~99% index fragmentation**.
- **The latest SQL Server 2025 does not change UUID sorting**: Microsoft kept the 1998 byte comparison order intact for backward compatibility, meaning UUIDv7 suffers the exact same fragmentation penalty on modern instances.
- **Naive byte swapping is not enough**: Moving the timestamp to bytes 10 to 15 leaves high-throughput inserts vulnerable to collisions within the same millisecond, still causing **~83% fragmentation**.
- **Monotonic sequence counters fix the B-tree**: Adding a 12-bit sequence counter in `rand_a` guarantees strict ordering even across thousands of inserts in the same millisecond, achieving **0.74% fragmentation**.
- **Identical efficiency to `NEWSEQUENTIALID()`**: Monotonic byte-swapped UUIDv7 achieves 99.94% page density and 1,755 pages for 200,000 rows on both engines, matching the database engine default while running entirely on the client.
- **Full DDD and EF Core support**: Client-side generation eliminates database roundtrips for primary keys, letting you assign foreign keys and stream events before calling `SaveChanges()`.

If you are building .NET microservices on SQL Server, do not blindly swap `Guid.NewGuid()` for `Guid.CreateVersion7()`. Drop in the monotonic byte-swapper, keep your B-trees healthy, and enjoy the best of both worlds.

## Resources

- [RFC 9562: Universally Unique Identifiers (UUIDs)](https://www.rfc-editor.org/rfc/rfc9562.html) - The official standard covering the UUIDv7 layout (Section 5.7) and monotonic sequence counters (Section 6.2).
- [.NET Runtime SQLGuid.cs Source Code](https://github.com/dotnet/runtime/blob/33baf8ee337b20dd0f184b69a6f09be92850bf9e/src/libraries/System.Data.Common/src/System/Data/SQLTypes/SQLGuid.cs#L116) - The internal `rgiGuidOrder` lookup array that governs SQL Server byte comparison order.
- [Microsoft Learn: Guid.CreateVersion7 Method](https://learn.microsoft.com/en-us/dotnet/api/system.guid.createversion7) - Official .NET documentation for native UUIDv7 creation in .NET 9 and later.
- [Microsoft Learn: sys.dm_db_index_physical_stats](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-views/sys-dm-db-index-physical-stats-transact-sql) - Reference documentation for the DMV used to evaluate leaf fragmentation and page space usage.
- [Medo.Uuid7 FillBytes7MsSql Source Code](https://github.com/medo64/Medo.Uuid7/blob/4b8ccbae25882bc3677157c1fd7764f3a1d7f571/src/Medo.Uuid7/Uuid7.Implementation.cs#L77) - Josip Medved's C# implementation for formatting UUIDv7 into SQL Server binary order.
- [SQLskills: GUIDs as PRIMARY KEYs and Clustering Keys](https://www.sqlskills.com/blogs/kimberly/guids-as-primary-keys-andor-the-clustering-key-the-ultimate-guide/) - Kimberly Tripp's deep dive into random GUID page splits, page density decay, and buffer cache bloat.
- [Taming the UUID Beast (Part 1)](/posts/taming-the-uuid-beast-how-to-avoid-clustered-index-fragmentation-in-sql-server/) - The February 2025 predecessor post demonstrating random GUID fragmentation versus `NEWSEQUENTIALID()`.




