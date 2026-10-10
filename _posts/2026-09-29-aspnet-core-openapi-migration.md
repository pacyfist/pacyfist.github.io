---
tags:
- dotnet
- aspnetcore
- openapi
- scalar
categories:
- dotnet
- architecture
title: 'ASP.NET Core OpenAPI Migration: Ditching Swashbuckle'
---

I have a confession to make. When I upgraded my first Web API project to .NET 9 and loaded `localhost:5001/swagger` in Chrome, I spent twenty minutes checking my reverse proxy config because the browser returned a blank 404.

Nothing was wrong with my proxy. The green-and-white Swagger UI dashboard we all relied on for eight years was simply gone.

For nearly a decade, running `dotnet new webapi` quietly installed `Swashbuckle.AspNetCore`. It was the default way to document ASP.NET Core APIs. But behind the scenes, Swashbuckle had stalled, piling up unmerged pull requests, security alerts, and zero support for modern OpenAPI 3.1 features.

In .NET 9, Microsoft pulled the plug and removed Swashbuckle from the default templates. In its place sits a new native document generator called `Microsoft.AspNetCore.OpenApi`.

The catch? It generates the raw JSON spec, but ships with **no user interface at all**. Think of OpenAPI as the raw JSON blueprint describing your endpoints, and Swagger UI or Scalar as the interactive web client that renders it.

To get a working API explorer back, the .NET community moved to **Scalar**. Here is how to complete the migration, ditch the abandoned packages, and fix the two configuration traps everyone hits along the way.

## Why Swashbuckle Got Dropped

Swashbuckle served the community well, but it suffered from three fundamental problems:

1. **Maintainer burnout:** The repository became inactive. Bug fixes sat unreviewed for months, and security warnings lingered in production pipelines.
2. **Reflection and Native AOT:** Swashbuckle relied heavily on runtime reflection. Native AOT strips out unused code at compile time for tiny, instant-start binaries. Because Swashbuckle looked up types dynamically at runtime, the compiler could not guarantee what was safe to trim, lighting up build logs with warnings.
3. **Monolithic design:** Swashbuckle bundled OpenAPI specification generation and the Swagger UI renderer into a single package. 

Microsoft decoupled those responsibilities. The framework now owns the JSON document generation through `Microsoft.AspNetCore.OpenApi`, letting you choose whatever modern UI you want on top.

## Swapping the NuGet Packages

First, remove the legacy Swashbuckle package from your project:

```bash
dotnet remove package Swashbuckle.AspNetCore
```

```text
info : Removing PackageReference for 'Swashbuckle.AspNetCore' from project '/home/eich/Projects/TaskApi/TaskApi.csproj'.
```

Next, install Microsoft's native OpenAPI generator and the Scalar UI package:

```bash
dotnet add package Microsoft.AspNetCore.OpenApi
dotnet add package Scalar.AspNetCore
```

```text
Determining projects to restore...
Writing /tmp/tmpK9vL12/obj/project.assets.json
Restored /home/eich/Projects/TaskApi/TaskApi.csproj (in 320 ms).
```

## The Baseline Setup

In your `Program.cs`, replace the old `AddSwaggerGen()` and `UseSwaggerUI()` calls:

```csharp
using Scalar.AspNetCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();

// 1. Register native OpenAPI generation
builder.Services.AddOpenApi();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    // 2. Expose the OpenAPI JSON document at /openapi/v1.json
    app.MapOpenApi();

    // 3. Serve the interactive Scalar documentation at /scalar/v1
    app.MapScalarApiReference();
}

app.MapControllers();
app.Run();
```

Fire up your application and navigate to `http://localhost:5001/scalar/v1`. 

Instead of the dated 2016 Swagger UI layout, you get a clean, dark-mode dashboard that looks like Stripe documentation. It includes an interactive API client, automatic search, and ready-to-copy code snippets in C#, Python, JavaScript, and cURL.

If all your endpoints are public and unauthenticated, you are done. But in real-world APIs, this is where two nasty surprises show up.

## Trap 1: JWT Bearer Authentication

In Swashbuckle, adding a JWT Bearer input box required calling `c.AddSecurityDefinition("Bearer", ...)` inside `AddSwaggerGen`.

In `Microsoft.AspNetCore.OpenApi`, there is no built-in fluent helper for Bearer auth. If you leave the configuration empty, Scalar displays your endpoints without an authorization button, and you cannot test protected routes.

To add security schemes to the native generator, you write a **document transformer**. Think of it as a post-processing hook: after .NET builds the initial OpenAPI schema, your transformer gets to inspect and modify the document in memory right before it gets served as JSON.

Create a new file named `BearerSecuritySchemeTransformer.cs`:

```csharp
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.OpenApi;
using Microsoft.OpenApi.Models;

public sealed class BearerSecuritySchemeTransformer(
    IAuthenticationSchemeProvider authenticationSchemeProvider) : IOpenApiDocumentTransformer
{
    public async Task TransformAsync(
        OpenApiDocument document,
        OpenApiDocumentTransformerContext context,
        CancellationToken cancellationToken)
    {
        var schemes = await authenticationSchemeProvider.GetAllSchemesAsync();
        if (!schemes.Any(s => s.Name == "Bearer"))
        {
            return;
        }

        // Define the Bearer scheme in Components
        var securityScheme = new OpenApiSecurityScheme
        {
            Type = SecuritySchemeType.Http,
            Scheme = "bearer",
            BearerFormat = "JWT",
            In = ParameterLocation.Header,
            Description = "Enter your JWT Bearer token."
        };

        document.Components ??= new OpenApiComponents();
        document.Components.SecuritySchemes ??= new Dictionary<string, OpenApiSecurityScheme>();
        document.Components.SecuritySchemes["Bearer"] = securityScheme;

        // Apply the requirement across all operations
        var securityRequirement = new OpenApiSecurityRequirement
        {
            [new OpenApiSecurityScheme
            {
                Reference = new OpenApiReference
                {
                    Id = "Bearer",
                    Type = ReferenceType.SecurityScheme
                }
            }] = Array.Empty<string>()
        };

        foreach (var operation in document.Paths.Values.SelectMany(p => p.Operations.Values))
        {
            operation.Security.Add(securityRequirement);
        }
    }
}
```

Now, wire the transformer into `AddOpenApi` inside `Program.cs`:

```csharp
builder.Services.AddOpenApi(options =>
{
    options.AddDocumentTransformer<BearerSecuritySchemeTransformer>();
});
```

Refresh `/scalar/v1`. An **Authorize** button appears in the top navigation bar. Enter your token once, and Scalar attaches the `Authorization: Bearer <token>` header to every test request you send.

## Trap 2: XML Comments Are Now Automatic

Remember how Swashbuckle forced you to write file path reflection code just to load your triple-slash XML comments?

```csharp
// The old Swashbuckle ritual we all copy-pasted:
var xmlFile = $"{Assembly.GetExecutingAssembly().GetName().Name}.xml";
options.IncludeXmlComments(Path.Combine(AppContext.BaseDirectory, xmlFile));
```

With `Microsoft.AspNetCore.OpenApi`, you can delete that entire block. The new framework engine detects XML documentation files automatically.

Open your `.csproj` and ensure XML file generation is turned on:

```xml
<PropertyGroup>
  <GenerateDocumentationFile>true</GenerateDocumentationFile>
  <!-- Suppress missing XML comment warnings for internal code -->
  <NoWarn>$(NoWarn);1591</NoWarn>
</PropertyGroup>
```

Add standard triple-slash comments to your controller actions or Minimal API routes:

```csharp
/// <summary>
/// Retrieves an order by its unique identifier.
/// </summary>
/// <param name="id">The GUID identifier of the order.</param>
/// <response code="200">The order was found and returned.</response>
/// <response code="404">No order matches the supplied identifier.</response>
[HttpGet("{id:guid}")]
[ProducesResponseType(typeof(OrderDto), StatusCodes.Status200OK)]
[ProducesResponseType(StatusCodes.Status404NotFound)]
public async Task<IActionResult> GetById(Guid id)
{
    // ...
}
```

The native generator reads the `<summary>`, `<param>`, and `<response>` tags straight into the OpenAPI document. Scalar formats them into clear documentation blocks with zero extra configuration.

## Customizing the Scalar Theme

Scalar gives you several built-in themes and client settings out of the box. You can configure them fluently in `MapScalarApiReference`:

```csharp
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();

    app.MapScalarApiReference(options =>
    {
        options
            .WithTitle("Customer Orders API")
            .WithTheme(ScalarTheme.Moon)
            .WithDefaultHttpClient(ScalarTarget.CSharp, ScalarClient.HttpClient);
    });
}
```

- `WithTheme(ScalarTheme.Moon)` applies a modern high-contrast dark theme.
- `WithDefaultHttpClient(ScalarTarget.CSharp, ScalarClient.HttpClient)` defaults the interactive code preview tab to C# `HttpClient` rather than cURL.

## Summary

- **Swashbuckle is no longer the default:** Microsoft dropped it in .NET 9 due to project abandonment, lack of OpenAPI 3.1 support, and Native AOT warnings.
- **Native document generation:** `builder.Services.AddOpenApi()` generates high-performance OpenAPI specs natively at `/openapi/v1.json`, but ships no UI.
- **Scalar is the modern replacement:** `Scalar.AspNetCore` plugs in via `app.MapScalarApiReference()` to provide a polished interactive API reference at `/scalar/v1`.
- **JWT auth requires a transformer:** Use `IOpenApiDocumentTransformer` to inject the `OpenApiSecurityScheme` and requirements into your document.
- **XML comments just work:** Enable `<GenerateDocumentationFile>` in your project file, and the framework automatically populates descriptions without reflection boilerplate.

If you are upgrading your APIs to .NET 9 or .NET 10, do not try to keep unmaintained Swashbuckle packages on life support. Switch to native OpenAPI with Scalar, clean up your boilerplate, and enjoy a much better developer experience.

## Resources

- [Microsoft Learn: OpenAPI Support in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/openapi/overview) - Official guide for configuring `Microsoft.AspNetCore.OpenApi` in .NET 9 and later.
- [GitHub: OpenApiEndpointRouteBuilderExtensions.cs](https://github.com/dotnet/aspnetcore/blob/af22effae4069a5dfb9b0735859de48820104f5b/src/OpenApi/src/Extensions/OpenApiEndpointRouteBuilderExtensions.cs#L24-L58) - Source code implementation for `MapOpenApi` route registration in ASP.NET Core.
- [GitHub: OpenApiServiceCollectionExtensions.cs](https://github.com/dotnet/aspnetcore/blob/af22effae4069a5dfb9b0735859de48820104f5b/src/OpenApi/src/Extensions/OpenApiServiceCollectionExtensions.cs#L22-L65) - Source code implementation for `AddOpenApi` and dependency injection setup.
- [GitHub: AddBearerSecuritySchemeTransformer.cs](https://github.com/dotnet/aspnetcore/blob/af22effae4069a5dfb9b0735859de48820104f5b/src/OpenApi/sample/Transformers/AddBearerSecuritySchemeTransformer.cs#L12-L33) - Official ASP.NET Core sample demonstrating the Bearer security scheme transformer.
- [Scalar GitHub Repository](https://github.com/scalar/scalar) - Documentation, theming guides, and package releases for the Scalar API client.
