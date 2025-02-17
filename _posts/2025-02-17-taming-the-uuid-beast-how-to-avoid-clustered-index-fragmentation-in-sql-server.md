---
tags: ["sqlserver", "tsql", "dba"]
categories: ["sqlserver", "tsql"]
title: "Taming the UUID Beast: How to Avoid Clustered Index Fragmentation in SQL Server"
image:
  path: /assets/img/2025-02-17/main.jpg
  alt: I have seen this beast so many times!
---

Hey everyone, your friendly neighborhood developer *is* back with another deep dive! Today, we're going to wrestle with a common performance killer: **index fragmentation**, specifically when using `UNIQUEIDENTIFIER` (UUID) as your clustered index.

### What's Fragmentation Anyway?

Imagine your data pages like houses on a street, neatly organized by address (in our case, the index key). Now, imagine someone randomly moves houses, builds new ones in between, and leaves empty lots. That's fragmentation!

In SQL Server, **fragmentation** happens when the logical order of your index (the order SQL Server uses to find data) doesn't match the physical order on disk. This leads to:

*   **Slower queries:** SQL Server has to jump around the disk to find the next piece of data.
*   **Increased I/O:** More disk reads mean more time spent waiting.
*   **Larger index size:** Empty spaces (gaps) in your data pages waste space.

### The UUID Fragmentation Problem

`UNIQUEIDENTIFIER` (UUID/GUID) is a 128-bit value often used as a primary key. It's great for generating unique IDs across multiple systems. However, the standard `NEWID()` function produces **random** UUIDs. This randomness is the root of our fragmentation problem.

Here's why random UUIDs cause chaos:

1.  **Inserts all over the place:** New rows with random UUIDs get inserted in the middle of existing data pages, forcing SQL Server to split pages and move data around.
2.  **Page Splits:** When a page is full and a new row needs to be inserted in the middle, SQL Server splits the page into two, creating fragmentation.
3.  **Random Order:** The physical order of the data doesn't match the logical (indexed) order.

Let's see this in action with a demo:

```sql
CREATE TABLE FragmentedTable (
    ID UNIQUEIDENTIFIER PRIMARY KEY CLUSTERED DEFAULT NEWID(),
    SomeData VARCHAR(200)
);

-- Insert a large number of rows with random UUIDs using a set-based approach
DECLARE @NumRows BIGINT = 1000000;  -- Set to 1 million
INSERT INTO FragmentedTable (SomeData)
SELECT TOP (@NumRows) 'Some Data'
FROM (
	SELECT
		1 as 'Ignored'
	FROM   sys.objects a
			CROSS JOIN sys.objects b
			CROSS JOIN sys.objects c
			CROSS JOIN sys.objects d
	) as t

-- Check the fragmentation level
SELECT
    OBJECT_NAME(ips.object_id) AS TableName,
    ips.index_id,
    index_type_desc,
    index_level,
    avg_fragmentation_in_percent,
    fragment_count,
    page_count
FROM sys.dm_db_index_physical_stats(DB_ID(), OBJECT_ID('FragmentedTable'), NULL, NULL, 'DETAILED') ips
ORDER BY avg_fragmentation_in_percent DESC;

-- Clean up the table
DROP TABLE FragmentedTable;
```

Run this code in your SQL Server Management Studio (SSMS) and see the `avg_fragmentation_in_percent` column. You'll likely see a high percentage, indicating significant fragmentation. On my database, we almost hit 100%, which is *kind* of impressive, don't you think?

|    TableName    | index_id | index_type_desc | index_level | avg_fragmentation_in_percent | fragment_count | page_count |
|:---------------:|:--------:|:---------------:|:-----------:|:----------------------------:|:--------------:|:----------:|
| FragmentedTable |     1    | CLUSTERED INDEX |      0      |       99.3622264096246       |      6899      |    6899    |
| FragmentedTable |     1    | CLUSTERED INDEX |      1      |            96.875            |       32       |     32     |
| FragmentedTable |     1    | CLUSTERED INDEX |      2      |               0              |        1       |      1     |

### The `NEWSEQUENTIALID()` Solution

SQL Server offers a special function called `NEWSEQUENTIALID()`. It generates UUIDs that are **mostly** sequential. This means new IDs are generally larger than existing ones. Using `NEWSEQUENTIALID()` can dramatically reduce fragmentation because new rows are mostly inserted at the end of the table, avoiding page splits.

**Important Note:** `NEWSEQUENTIALID()` has some limitations:

*   Can only be used on columns with the `UNIQUEIDENTIFIER` data type.
*   Can only be used as a `DEFAULT` constraint on a table.
*   It guarantees uniqueness **only** within a single server instance.
*   After a server restart, `NEWSEQUENTIALID()` may not pick up exactly where it left off, potentially creating a small amount of fragmentation.

Here's the code demonstrating `NEWSEQUENTIALID()`:

```sql
CREATE TABLE NonFragmentedTable (
    ID UNIQUEIDENTIFIER PRIMARY KEY CLUSTERED DEFAULT NEWSEQUENTIALID(),
    SomeData VARCHAR(200)
);

-- Insert a large number of rows with random UUIDs using a set-based approach
-- Insert a large number of rows with random UUIDs using a set-based approach
DECLARE @NumRows BIGINT = 1000000;  -- Set to 1 million
INSERT INTO NonFragmentedTable (SomeData)
SELECT TOP (@NumRows) 'Some Data'
FROM (
	SELECT
		1 as 'Ignored'
	FROM   sys.objects a
			CROSS JOIN sys.objects b
			CROSS JOIN sys.objects c
			CROSS JOIN sys.objects d
	) as t

-- Check the fragmentation level
SELECT
    OBJECT_NAME(ips.object_id) AS TableName,
    ips.index_id,
    index_type_desc,
    index_level,
    avg_fragmentation_in_percent,
    fragment_count,
    page_count
FROM sys.dm_db_index_physical_stats(DB_ID(), OBJECT_ID('NonFragmentedTable'), NULL, NULL, 'DETAILED') ips
ORDER BY avg_fragmentation_in_percent DESC;

-- Clean up the table
DROP TABLE NonFragmentedTable;
```

Run this code, and you'll see a much lower `avg_fragmentation_in_percent`. The index is more organized, and your queries will be faster. A million rows is nothing for this table!

|      TableName     | index_id | index_type_desc | index_level | avg_fragmentation_in_percent | fragment_count | page_count |
|:------------------:|:--------:|:---------------:|:-----------:|:----------------------------:|:--------------:|:----------:|
| NonFragmentedTable |     1    | CLUSTERED INDEX |      0      |       0.660276890308839      |       34       |    4695    |
| NonFragmentedTable |     1    | CLUSTERED INDEX |      1      |               0              |       31       |     31     |
| NonFragmentedTable |     1    | CLUSTERED INDEX |      2      |               0              |        1       |      1     |

I even tried to insert 10,000,000 rows, and fragmentation remained under 1%.

|      TableName     | index_id | index_type_desc | index_level | avg_fragmentation_in_percent | fragment_count | page_count |
|:------------------:|:--------:|:---------------:|:-----------:|:----------------------------:|:--------------:|:----------:|
| NonFragmentedTable |     1    | CLUSTERED INDEX |      1      |       0.955414012738854      |       314      |     314    |
| NonFragmentedTable |     1    | CLUSTERED INDEX |      0      |       0.670940808110929      |       327      |    46949   |
| NonFragmentedTable |     1    | CLUSTERED INDEX |      2      |               0              |        1       |      1     |

### Choosing the Right Approach

*   If you **need** truly random UUIDs for global uniqueness across different systems (e.g., distributed applications), you might have to accept some fragmentation and schedule regular index maintenance (rebuilds or reorganizations).
*   If you primarily need uniqueness within a single SQL Server instance and can tolerate *near* sequentiality, `NEWSEQUENTIALID()` is the clear winner for performance.

### In Conclusion

`UNIQUEIDENTIFIER` columns are a great choice for primary keys. However, using `NEWID()` can lead to significant index fragmentation, impacting performance. Use `NEWSEQUENTIALID()` whenever possible to mitigate fragmentation and keep your SQL Server humming. Remember to analyze your specific needs and choose the approach that best balances uniqueness and performance.

Happy clustering!
