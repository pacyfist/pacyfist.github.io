---
tags: ["csharp", "entity framework"]
categories: ["csharp", "entity framework"]
title: "Entity Framework 7: Bulk Updates and Deletes Made Easy!"
---

Guess what? I've been living under a rock because I just found out that entity framework in version 7 finally fixed one of its massive blunders. Can you believe it? The API got a serious makeover for handling bulk updates and deletes, and boy, it's looking sweet!

## Enhanced UPDATE

Picture this: We goofed up and mistakenly stored a million "Kowalski" entries in our database as "Kowalki". Ouch! Fixing this used to be a nightmare. We had to download all the entries, tweak just one property, and then save all those changes. It was a painfully slow process that involved moving tons of data around. But guess what? I've got some fantastic news! Now, we don't have to go through all that hassle anymore. Drumroll, please... we can simply write:

```csharp
await context.Users
    .Where(u => u.Name == "Kowalki")
    .ExecuteUpdateAsync(x => x.SetProperty(u => u.Name, "Kowalski"), cancellationToken);
```

and like magic, the entity framework will perform its wizardry and seamlessly translate into SQL below.

```sql
UPDATE Users AS u
SET
u.Name = N'Kowalski'
SELECT 1
FROM Users AS u
WHERE u.Name == N'Kowalki'
```

In the blink of an eye, the SQL Server will work its lightning-fast wonders, updating the data within milliseconds. Voila! My life just got a little easier!

## Enhanced DELETE

And what if, by some stroke of bad luck, we find ourselves wanting to eliminate every trace of "Duda" from the database? Is there a glimmer of hope for us to achieve this with a single line of code? You betcha! Yes, indeed there is!

```csharp
await context.Users
    .Where(u => u.Name == "Duda")
    .ExecuteDeleteAsync(cancellationToken);
```

Sit back and relish the sheer elegance of the SQL code below. Doesn't it exude the pristine purity of a freshly purchased car? And you can bet your bottom dollar it's just as swift as it looks!

```sql
DELETE FROM [u]
FROM [Users] AS [u]
WHERE [u].[Name] = N'Duda'
```

After an agonizing wait and enduring six versions of workarounds, us developers have finally been blessed with a feature lack off which prompted some of us to switch to Dapper. But fret no more! We can now bid farewell to that migration. To all you Dapper aficionados out there, we extend a warm welcome back into the fold. We've missed you!
