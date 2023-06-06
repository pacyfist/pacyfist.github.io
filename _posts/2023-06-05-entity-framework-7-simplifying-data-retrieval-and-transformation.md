---
tags: ["csharp", "entity framework"]
categories: ["csharp", "entity framework"]
title: "Entity Framework 7: Simplifying Data Retrieval and Transformation!"
---

Well, it seems like I've been fumbling around with entity framework like a clumsy monkey! Turns out there's a ridiculously slick method to fetch data from a database, and I've been oblivious to it all this time. Talk about missing the coding boat!

## Configuration

Let's kick off our journey with a delightful and uncomplicated database structure

```csharp
public class Category
{
    public int CategoryId { get; set; }
    public string Name { get; set; }
    public IEnumerable<SubCategory> SubCategories { get; set; }
}

public class SubCategory
{
    public int SubCategoryId { get; set; }
    public string Name { get; set; }
    public IEnumerable<Product> Products { get; set; }
}

public class Product
{
    public int ProductId { get; set; }
    public string Name { get; set; }
    public decimal Price { get; set; }
}
```

and some DTOs so basic they make a slice of bread look complex.

```csharp
public class CategoryDTO
{
    public string Name { get; set; }
    public IEnumerable<SubCategoryDTO> SubCategories { get; set; }
}

public class SubCategoryDTO
{
    public string Name { get; set; }
    public IEnumerable<ProductDTO> Products { get; set; }
}

public class ProductDTO
{
    public string Name { get; set; }
    public decimal Price { get; set; }
}
```

## Out with the old

In my usual shenanigans, I would often snatch the data first and worry about transforming it into something useful later

```csharp
var categories = context.Categories
   .Include(c => c.SubCategories)
   .ThenInclude(sc => sc.Products)
   .ToList();

var dtos = categories.Adapt<IList<CategoryDTO>>();
```

or on occasion, I'd level up and merge those steps like a coding ninja, achieving a glorious union of data retrieval and transformation.

```csharp
var dtos = context.Categories
    .Include(c => c.SubCategories)
    .ThenInclude(sc => sc.Products)
    .Select(c => c.Adapt<CategoryDTO>())
    .ToList();
```

Both of these approaches end up producing SQL statement that is somewhat needlessly convoluted. However, fear not, for the SQL query optimizer possesses the magical ability to effortlessly eliminate that surplus select statement before executing the query so no harm will happen to the database.

```sql
SELECT [c].[CategoryId], [c].[Name], [t].[SubCategoryId], [t].[CategoryId], [t].[Name], [t].[ProductId], [t].[Name0], [t].[Price], [t].[SubCategoryId0]
FROM [Categories] AS [c]
LEFT JOIN (
    SELECT [s].[SubCategoryId], [s].[CategoryId], [s].[Name], [p].[ProductId], [p].[Name] AS [Name0], [p].[Price], [p].[SubCategoryId] AS [SubCategoryId0]
    FROM [SubCategory] AS [s]
    LEFT JOIN [Product] AS [p] ON [s].[SubCategoryId] = [p].[SubCategoryId]
) AS [t] ON [c].[CategoryId] = [t].[CategoryId]
ORDER BY [c].[CategoryId], [t].[SubCategoryId]
```

## In with the new

But lo and behold, the clever minds behind Entity Framework have seemingly conspired to persuade us to bid farewell to the mapper altogether, promising that such abandonment shall grant us the sweet liberation of simplified coding. It appears that relinquishing the mapper will pave the way for a smoother journey, rendering a handful of tasks considerably easier.

```csharp
var dtos = context.Categories.Select(c => new CategoryDTO()
{
    Name = c.Name,
    SubCategories = c.SubCategories.Select(sc => new SubCategoryDTO()
    {
        Name = sc.Name,
        Products = sc.Products.Select(p => new ProductDTO()
        {
            Name = p.Name,
            Price = p.Price
        })
    })
}).ToList();
```

By uttering this enchanting statement, we witness a subtle transformation in the SQL realm

```sql
SELECT [c].[Name], [c].[CategoryId], [t].[Name], [t].[SubCategoryId], [t].[Name0], [t].[Price], [t].[ProductId]
FROM [Categories] AS [c]
LEFT JOIN (
    SELECT [s].[Name], [s].[SubCategoryId], [p].[Name] AS [Name0], [p].[Price], [p].[ProductId], [s].[CategoryId]
    FROM [SubCategory] AS [s]
    LEFT JOIN [Product] AS [p] ON [s].[SubCategoryId] = [p].[SubCategoryId]
) AS [t] ON [c].[CategoryId] = [t].[CategoryId]
ORDER BY [c].[CategoryId], [t].[SubCategoryId]
```

which bestows upon us a trio of delightful enhancements

1. Gone are the days of fetching columns like `CategoryId` and `SubCategoryId` twice from the database. We now enjoy the luxury of a single request, sparing us unnecessary duplication.

2. Say goodbye to the repetitive chore of calling `Include` and `ThenInclude` for every new table you introduce. With this newfound glory, finding a field of missing data becomes a distant nightmare, as debugging becomes a breeze.

3. Brace yourself for the beauty of explicit conversion to DTOs. No more hidden surprises lurking within the depths of mapper configuration. The conversion process now stands boldly before us, making our coding endeavors crystal clear.
