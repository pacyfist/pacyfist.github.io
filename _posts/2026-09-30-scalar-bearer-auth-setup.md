---
tags: ["dotnet", "aspnetcore", "openapi", "scalar", "jwt"]
categories: ["dotnet", "webapi"]
title: "Scalar Bearer Auth Setup: Where Did My Padlock Go"
image:
  path: /assets/img/2026-09-30/main.jpg
  alt: A tactile security console with an illuminated token key slot powering connected API cards.
---

I had a nagging itch after migrating a Minimal API to Scalar on `http://127.0.0.1:5055`: the documentation looked crisp, but clicking "Test Request" on `/api/secret` failed instantly with an unauthenticated `401 Unauthorized`.

There was no padlock icon next to the route. There was no "Authorize" button in the header. Even though the endpoint had `.RequireAuthorization()`, Scalar treated it like a public route and sent requests without credentials.

In legacy Swashbuckle, two lines of `c.AddSecurityDefinition` and `c.AddSecurityRequirement` lit up your entire API with green padlocks. In native `Microsoft.AspNetCore.OpenApi`, the generator produces a raw OpenAPI 3.1 document without making assumptions about your routes. If you do not explicitly map your authorization metadata to the OpenAPI operation, your secured routes stay naked in the docs.

Here is why the padlock disappears and how to get it back in three small steps.

## The Mental Model: Spec Generator vs. UI Renderer

In .NET 9 and .NET 10, Microsoft split API documentation into two clean layers:

1. **The specification engine:** `Microsoft.AspNetCore.OpenApi` generates the raw OpenAPI JSON document at `/openapi/v1.json`.
2. **The interactive explorer:** `Scalar.AspNetCore` downloads that JSON document and renders an interactive web UI at `/scalar/v1`.

Think of the OpenAPI document as an architectural blueprint and Scalar as the general contractor. If the blueprint does not draw a lock on the door, the contractor will not install one.

Adding `.RequireAuthorization()` to an endpoint protects the route at runtime in Kestrel. But Microsoft's native OpenAPI generator is unopinionated - it does not inspect runtime authorization attributes by default. If you want a padlock in Scalar, you must explicitly describe your security scheme and attach it to your endpoints.

## Step 1: Declaring the Bearer Scheme in OpenAPI Components

In legacy Swashbuckle, you called `AddSecurityDefinition("Bearer", ...)`. In native OpenAPI, we use a document transformer to add the definition to `document.Components.SecuritySchemes`.

Why is this step required? Without a declared scheme in `components.securitySchemes`, OpenAPI 3.1 documents cannot describe authorization mechanisms. Any API client generator or interactive UI assumes the API is completely unauthenticated.

If you paste an old Swashbuckle or .NET 8 code snippet into a .NET 10 project, the compiler stops you with two errors:

```text
Program.cs(5,25): error CS0234: The type or namespace name 'Models' does not exist in the namespace 'Microsoft.OpenApi' (are you missing an assembly reference?)
```

```text
Program.cs(37,9): error CS0019: Operator '??=' cannot be applied to operands of type 'IDictionary<string, IOpenApiSecurityScheme>' and 'Dictionary<string, OpenApiSecurityScheme>'
```

In .NET 10 (`Microsoft.OpenApi` 2.x), the types moved out of `Microsoft.OpenApi.Models` into `Microsoft.OpenApi`. The `SecuritySchemes` dictionary is also typed to the interface `IOpenApiSecurityScheme`.

Here is the correct document transformer registered in `Program.cs`:

```csharp
builder.Services.AddOpenApi(options =>
{
    options.AddDocumentTransformer((document, context, cancellationToken) =>
    {
        document.Components ??= new OpenApiComponents();
        document.Components.SecuritySchemes ??= new Dictionary<string, IOpenApiSecurityScheme>();
        document.Components.SecuritySchemes["Bearer"] = new OpenApiSecurityScheme
        {
            Type = SecuritySchemeType.Http,
            Scheme = "bearer",
            BearerFormat = "JWT",
            Description = "Enter your JWT Bearer token."
        };
        return Task.CompletedTask;
    });
});
```

Notice the null-coalescing assignment (`??=`). `document.Components` and `document.Components.SecuritySchemes` both start as null. Checking and initializing them prevents a runtime `NullReferenceException` when your application builds the OpenAPI document.

## The Missing Padlock Trap

Most developers add the document transformer, start their application, and assume their work is done.

Why run this test? We need to verify whether declaring a security scheme is enough for OpenAPI to automatically protect endpoints marked with `.RequireAuthorization()`. If it fails, our documentation stays broken.

Let's test the endpoint on `http://127.0.0.1:5055`:

```bash
curl -s http://127.0.0.1:5055/openapi/v1.json | jq .
```

```json
{
  "openapi": "3.1.1",
  "info": {
    "title": "ScalarAuthDemo | v1",
    "version": "1.0.0"
  },
  "servers": [
    {
      "url": "http://127.0.0.1:5055/"
    }
  ],
  "paths": {
    "/api/public": {
      "get": {
        "tags": [
          "ScalarAuthDemo"
        ],
        "responses": {
          "200": {
            "description": "OK"
          }
        }
      }
    },
    "/api/secret": {
      "get": {
        "tags": [
          "ScalarAuthDemo"
        ],
        "responses": {
          "200": {
            "description": "OK"
          }
        }
      }
    },
    "/api/auth/token": {
      "post": {
        "tags": [
          "ScalarAuthDemo"
        ],
        "responses": {
          "200": {
            "description": "OK"
          }
        }
      }
    }
  },
  "components": {
    "securitySchemes": {
      "Bearer": {
        "type": "http",
        "description": "Enter your JWT Bearer token.",
        "scheme": "bearer",
        "bearerFormat": "JWT"
      }
    }
  },
  "tags": [
    {
      "name": "ScalarAuthDemo"
    }
  ]
}
```

Look closely at `paths['/api/secret']`. Even though `/api/secret` has `.RequireAuthorization()` in C#, the generated JSON has zero `security` fields. Its definition looks identical to the public `/api/public` route.

Because the document omits the `security` requirement, Scalar has no way of knowing this route is protected. It shows no padlock, hides the token input, and fires unauthenticated requests.

Calling the route returns an unauthenticated error:

```bash
curl -s -i http://127.0.0.1:5055/api/secret
```

```text
HTTP/1.1 401 Unauthorized
Content-Length: 0
Date: Tue, 29 Sep 2026 21:31:10 GMT
Server: Kestrel
WWW-Authenticate: Bearer
```

Declaring the scheme in `components` is only step one. We also need to attach that scheme to individual operations.

## Step 2: Attaching Requirements with an Operation Transformer

Why is an operation transformer the right fix? Hardcoding security globally locks down anonymous endpoints like health checks and login routes. Omitting it leaves protected routes looking public. We need a selective transformer that inspects endpoint metadata for `IAuthorizeData` while honoring `IAllowAnonymous`.

In `Microsoft.OpenApi` 2.x, the dictionary key in `OpenApiSecurityRequirement` is an `OpenApiSecuritySchemeReference`, passing the scheme name and the active document context.

Here is the clean, reusable operation transformer class:

```csharp
public sealed class BearerSecurityOperationTransformer : IOpenApiOperationTransformer
{
    public Task TransformAsync(
        OpenApiOperation operation,
        OpenApiOperationTransformerContext context,
        CancellationToken cancellationToken)
    {
        var metadata = context.Description.ActionDescriptor.EndpointMetadata;

        if (metadata.OfType<IAuthorizeData>().Any() && !metadata.OfType<IAllowAnonymous>().Any())
        {
            operation.Security ??= new List<OpenApiSecurityRequirement>();
            operation.Security.Add(new OpenApiSecurityRequirement
            {
                [new OpenApiSecuritySchemeReference("Bearer", context.Document)] = new List<string>()
            });
        }

        return Task.CompletedTask;
    }
}
```

Register this transformer in your `AddOpenApi` configuration:

```csharp
builder.Services.AddOpenApi(options =>
{
    options.AddDocumentTransformer((document, context, cancellationToken) =>
    {
        document.Components ??= new OpenApiComponents();
        document.Components.SecuritySchemes ??= new Dictionary<string, IOpenApiSecurityScheme>();
        document.Components.SecuritySchemes["Bearer"] = new OpenApiSecurityScheme
        {
            Type = SecuritySchemeType.Http,
            Scheme = "bearer",
            BearerFormat = "JWT",
            Description = "Enter your JWT Bearer token."
        };
        return Task.CompletedTask;
    });

    options.AddOperationTransformer<BearerSecurityOperationTransformer>();
});
```

Now query `/openapi/v1.json` again:

```bash
curl -s http://127.0.0.1:5055/openapi/v1.json | jq .paths
```

```json
{
  "/api/public": {
    "get": {
      "tags": [
        "ScalarAuthDemo"
      ],
      "responses": {
        "200": {
          "description": "OK"
        }
      }
    }
  },
  "/api/secret": {
    "get": {
      "tags": [
        "ScalarAuthDemo"
      ],
      "responses": {
        "200": {
          "description": "OK"
        }
      },
      "security": [
        {
          "Bearer": []
        }
      ]
    }
  },
  "/api/auth/token": {
    "post": {
      "tags": [
        "ScalarAuthDemo"
      ],
      "responses": {
        "200": {
          "description": "OK"
        }
      }
    }
  }
}
```

`/api/secret` now carries `"security": [ { "Bearer": [] } ]`. The public and auth routes remain untouched. Scalar reads this definition and immediately renders the padlock icon on `/api/secret`.

## Step 3: Preselecting Bearer in the Scalar UI

Why configure Scalar options? Even with a valid OpenAPI document, users visiting the documentation would have to manually find the auth dropdown and pick the Bearer scheme every time. Configuring Scalar ensures the Bearer scheme is selected automatically.

Older tutorials set `PreferredSecurityScheme = "Bearer"`. In modern versions of `Scalar.AspNetCore`, that singular property is deprecated:

```text
ScalarAuthDemo/Program.cs(62,9): warning CS0618: 'ScalarAuthenticationOptions.PreferredSecurityScheme' is obsolete: 'This property is obsolete and will be removed in a future release. Use PreferredSecuritySchemes property to configure the preferred security scheme instead.' [/home/eich/Projects/pacyfist.github.io/experiments/scalar-bearer-auth/ScalarAuthDemo/ScalarAuthDemo.csproj]
```

Use the plural collection property `PreferredSecuritySchemes = ["Bearer"]`:

```csharp
app.MapScalarApiReference(options =>
{
    options.Title = "Scalar Auth Demo API";
    options.Authentication = new ScalarAuthenticationOptions
    {
        PreferredSecuritySchemes = ["Bearer"]
    };
});
```

We can verify how Scalar serves this configuration:

```bash
curl -s http://127.0.0.1:5055/scalar/v1
```

```html
<!doctype html>
<html>
<head>
    <title>Scalar Auth Demo API</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    
</head>
<body>
    
    <div id="app"></div>
    <script src="scalar.js"></script>
    <script type="module" src="scalar.aspnetcore.js"></script>
    <script type="module">
        import { initialize } from './scalar.aspnetcore.js'
        initialize(
        '%2Fscalar%2Fv1',
        false,
        {"authentication":{"preferredSecurityScheme":["Bearer"]},"favicon":"favicon.svg","_integration":"dotnet","sources":[{"title":"v1","url":"openapi/v1.json"}]},
        '')
    </script>
</body>
</html>
```

The configuration is embedded directly into `initialize()`: Scalar opens with the Bearer scheme ready for token input.

## Live Verification with cURL

Let's test all endpoints on the running Kestrel server.

First, verify that public routes remain accessible without credentials:

```bash
curl -s -i http://127.0.0.1:5055/api/public
```

```text
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Date: Tue, 29 Sep 2026 21:32:11 GMT
Server: Kestrel
Transfer-Encoding: chunked

{"status":"healthy","message":"Public endpoint, no auth required."}
```

Next, verify that calling the protected route without a token fails:

```bash
curl -s -i http://127.0.0.1:5055/api/secret
```

```text
HTTP/1.1 401 Unauthorized
Content-Length: 0
Date: Tue, 29 Sep 2026 21:32:14 GMT
Server: Kestrel
WWW-Authenticate: Bearer
```

Generate a signed JWT token from the token issuer endpoint:

```bash
curl -s -X POST http://127.0.0.1:5055/api/auth/token
```

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJodHRwOi8vc2NoZW1hcy54bWxzb2FwLm9yZy93cy8yMDA1LzA1L2lkZW50aXR5L2NsYWltcy9uYW1lIjoiTGFiVXNlciIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6IkFkbWluIiwiZXhwIjoxNzkwNzIxMTM2LCJpc3MiOiJodHRwczovL2xhYi5wYWN5ZmlzdC5kZXYiLCJhdWQiOiJodHRwczovL2xhYi5wYWN5ZmlzdC5kZXYifQ.M4vMeof0IrRpwUAh3tc1TfsskX7JXMVYHcvnlP-T6io",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

Call the protected route with the Bearer token header:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:5055/api/auth/token | jq -r .token)
curl -s -i -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5055/api/secret
```

```text
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Date: Tue, 29 Sep 2026 21:32:20 GMT
Server: Kestrel
Transfer-Encoding: chunked

{"status":"authorized","user":"LabUser","message":"Access granted to secret vault for LabUser!"}
```

Finally, verify that sending an invalid token is rejected by the JWT middleware:

```bash
curl -s -i -H "Authorization: Bearer invalid.garbage.token" http://127.0.0.1:5055/api/secret
```

```text
HTTP/1.1 401 Unauthorized
Content-Length: 0
Date: Tue, 29 Sep 2026 21:32:23 GMT
Server: Kestrel
WWW-Authenticate: Bearer error="invalid_token"
```

## The Complete Working Program.cs

Here is the entire self-contained application tested on .NET 10:

```csharp
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.OpenApi;
using Microsoft.IdentityModel.Tokens;
using Microsoft.OpenApi;
using Scalar.AspNetCore;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;

var builder = WebApplication.CreateBuilder(args);

var signingKey = new SymmetricSecurityKey(
    Encoding.UTF8.GetBytes("SuperSecretLabKeyForTestingScalarBearerAuth2026!"));

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer = "https://lab.pacyfist.dev",
            ValidAudience = "https://lab.pacyfist.dev",
            IssuerSigningKey = signingKey
        };
    });

builder.Services.AddAuthorization();

builder.Services.AddOpenApi(options =>
{
    // Step 1: Declare the "Bearer" security scheme in components
    options.AddDocumentTransformer((document, context, cancellationToken) =>
    {
        document.Components ??= new OpenApiComponents();
        document.Components.SecuritySchemes ??= new Dictionary<string, IOpenApiSecurityScheme>();
        document.Components.SecuritySchemes["Bearer"] = new OpenApiSecurityScheme
        {
            Type = SecuritySchemeType.Http,
            Scheme = "bearer",
            BearerFormat = "JWT",
            Description = "Enter your JWT Bearer token."
        };
        return Task.CompletedTask;
    });

    // Step 2: Attach security requirement to [Authorize] endpoints
    options.AddOperationTransformer<BearerSecurityOperationTransformer>();
});

var app = builder.Build();

app.UseAuthentication();
app.UseAuthorization();

app.MapOpenApi();

// Step 3: Configure Scalar UI with preferred security scheme
app.MapScalarApiReference(options =>
{
    options.Title = "Scalar Auth Demo API";
    options.Authentication = new ScalarAuthenticationOptions
    {
        PreferredSecuritySchemes = ["Bearer"]
    };
});

app.MapGet("/api/public", () => Results.Ok(new
{
    status = "healthy",
    message = "Public endpoint, no auth required."
}));

app.MapGet("/api/secret", (ClaimsPrincipal user) => Results.Ok(new
{
    status = "authorized",
    user = user.Identity?.Name,
    message = $"Access granted to secret vault for {user.Identity?.Name}!"
})).RequireAuthorization();

app.MapPost("/api/auth/token", () =>
{
    var claims = new[]
    {
        new Claim(ClaimTypes.Name, "LabUser"),
        new Claim(ClaimTypes.Role, "Admin")
    };
    var creds = new SigningCredentials(signingKey, SecurityAlgorithms.HmacSha256);
    var token = new JwtSecurityToken(
        issuer: "https://lab.pacyfist.dev",
        audience: "https://lab.pacyfist.dev",
        claims: claims,
        expires: DateTime.UtcNow.AddHours(1),
        signingCredentials: creds
    );
    return Results.Ok(new
    {
        token = new JwtSecurityTokenHandler().WriteToken(token),
        token_type = "Bearer",
        expires_in = 3600
    });
});

app.Run();

public sealed class BearerSecurityOperationTransformer : IOpenApiOperationTransformer
{
    public Task TransformAsync(
        OpenApiOperation operation,
        OpenApiOperationTransformerContext context,
        CancellationToken cancellationToken)
    {
        var metadata = context.Description.ActionDescriptor.EndpointMetadata;

        if (metadata.OfType<IAuthorizeData>().Any() && !metadata.OfType<IAllowAnonymous>().Any())
        {
            operation.Security ??= new List<OpenApiSecurityRequirement>();
            operation.Security.Add(new OpenApiSecurityRequirement
            {
                [new OpenApiSecuritySchemeReference("Bearer", context.Document)] = new List<string>()
            });
        }

        return Task.CompletedTask;
    }
}
```

## Summary

- **Native OpenAPI is unopinionated:** `Microsoft.AspNetCore.OpenApi` does not infer authorization requirements from `.RequireAuthorization()` by default.
- **Document transformers define the scheme:** Use `AddDocumentTransformer` to define `components.securitySchemes["Bearer"]` with null-safe dictionary initialization.
- **Operation transformers attach the lock:** Check endpoint metadata for `IAuthorizeData` (excluding `IAllowAnonymous`) and add `OpenApiSecurityRequirement` to the operation's `Security` list.
- **Microsoft.OpenApi 2.x type safety:** Use `OpenApiSecuritySchemeReference` as the requirement key, and import `Microsoft.OpenApi` rather than the old `.Models` namespace.
- **Scalar preferred schemes:** Set `PreferredSecuritySchemes = ["Bearer"]` in `ScalarAuthenticationOptions` to silence CS0618 and preselect the scheme in the UI.

Keep your transformers in dedicated sealed classes once your API grows beyond a single file. It keeps your `Program.cs` lean and gives you unit-testable OpenAPI pipeline steps.

## Resources

- [Microsoft Learn: OpenAPI Support in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/openapi/overview) - Official guide for configuring `Microsoft.AspNetCore.OpenApi` and transformers.
- [GitHub: AddBearerSecuritySchemeTransformer.cs](https://github.com/dotnet/aspnetcore/blob/af22effae4069a5dfb9b0735859de48820104f5b/src/OpenApi/sample/Transformers/AddBearerSecuritySchemeTransformer.cs#L12-L33) - Official ASP.NET Core sample demonstrating the Bearer security scheme transformer.
- [GitHub: OpenApiOperationTransformerContext.cs](https://github.com/dotnet/aspnetcore/blob/af22effae4069a5dfb9b0735859de48820104f5b/src/OpenApi/src/Transformers/OpenApiOperationTransformerContext.cs#L11-L32) - Source code implementation for the OpenAPI operation transformer context.
- [GitHub: ScalarAuthenticationOptions.cs](https://github.com/scalar/scalar/blob/0e5c088ccf1211e82122ff8478ffc389acf4d08e/integrations/dotnet/shared/src/Scalar.Shared/Options/Authentication/ScalarAuthenticationOptions.cs#L16-L38) - Source code showing the deprecation of `PreferredSecurityScheme` and addition of `PreferredSecuritySchemes`.
- [RFC 6750: The OAuth 2.0 Authorization Framework: Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750) - The Internet Engineering Task Force specification defining Bearer token headers and 401 challenge formats.
