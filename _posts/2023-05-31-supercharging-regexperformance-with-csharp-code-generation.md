---
tags: ["csharp", "regex", "code generators"]
categories: ["csharp", "code generators"]
title: "Supercharging Regex Performance with C# Code Generation"
---

I decided to dive deeper into the code generation feature of the Roselyn compiler. And guess what? I stumbled upon this mind-blowing discovery that can seriously boost the speed of regular expressions. I couldn't resist running some tests, and boy, oh boy, let me tell you what I uncovered. Brace yourself for some nerdy excitement!

I cooked up a pretty nifty regular expression to sniff out domains that might have a sneaky little asterisk (\*) hanging out at the start. It's like detective work for the digital world!

```text
^(\*\.)?([a-zA-Z0-9][a-zA-Z0-9-]*\.)+[a-zA-Z]{2,}$
```

Alright, folks, time to roll up our sleeves and get down to business with some performance testing. I'll be putting both a valid and an invalid case through the wringer to see if there's any noticeable difference between them.

```csharp
private const string ValidDomain = "*.google.com";
private const string InvalidDomain = "web.google.*";
```

I'm about to unleash the mother of all nightmare scenarios. Brace yourselves for a code snippet that'll make you question your very sanity. We're talking about a level of pure, unadulterated agony that will leave you begging for mercy.

```csharp
[Benchmark]
public bool DontDoThis()
{
    return new Regex(@"^(\*\.)?([a-zA-Z0-9][a-zA-Z0-9-]*\.)+[a-zA-Z]{2,}$")
        .IsMatch(ValidDomain);
}

[Benchmark]
public bool JustPleaseDont()
{
    return new Regex(@"^(\*\.)?([a-zA-Z0-9][a-zA-Z0-9-]*\.)+[a-zA-Z]{2,}$")
        .IsMatch(InvalidDomain);
}
```

Now that I've conquered that dreaded hurdle, I can finally delve into a pair of cases that hold true value. It's all about the clean and tidy utilization of the static `Regex` class. I can't help but wonder if this class knows how to optimize its repeated execution with cache. Time to put it to the test and see if it's as smart as it claims to be!

```csharp
[Benchmark]
public bool ValidRegexMatch()
{
    return Regex.IsMatch(
        ValidDomain,
        @"^(\*\.)?([a-zA-Z0-9][a-zA-Z0-9-]*\.)+[a-zA-Z]{2,}$");
}

[Benchmark]
public bool InvalidRegexMatch()
{
    return Regex.IsMatch(
        InvalidDomain,
        @"^(\*\.)?([a-zA-Z0-9][a-zA-Z0-9-]*\.)+[a-zA-Z]{2,}$");
}
```

No more leaving things up to chance! This time, I'm taking matters into my own hands. I'll extract a single, glorious instance of the `Regex` class that will be created only once. Oh, the sweet scent of speed that's wafting through the air!

```csharp
private static readonly Regex DomainRegex
    = new Regex(@"^(\*\.)?([a-zA-Z0-9][a-zA-Z0-9-]*\.)+[a-zA-Z]{2,}$");

[Benchmark]
public bool ValidPatternMatch()
{
    return DomainRegex.IsMatch(ValidDomain);
}

[Benchmark]
public bool InvalidPatternMatch()
{
    return DomainRegex.IsMatch(InvalidDomain);
}
```

And voila! We've reached the grand finale of this exhilarating journey. Brace yourselves, because I'm about to unleash the crème de la crème of code generation technology. With just a single attribute, I can infuse a humble method with the awe-inspiring power of regular expressions. Watch in awe as the code generator springs into action, fashioning in secrecy a custom-tailored `RegexGenerator.g.cs` file containing a class that perfectly suits my every need.

```csharp
[GeneratedRegex(
    @"^(\*\.)?([a-zA-Z0-9][a-zA-Z0-9-]*\.)+[a-zA-Z]{2,}$",
    RegexOptions.IgnoreCase,
    "en-US")]
private static partial Regex DomainValidator();


[Benchmark]
public bool ValidGeneratedMatch()
{
    return DomainValidator().IsMatch(ValidDomain);
}

[Benchmark]
public bool InvalidGeneratedMatch()
{
    return DomainValidator().IsMatch(InvalidDomain);
}
```

But let's face it, you're not here to read through lines of my code. You're eagerly awaiting the moment when I reveal the benchmark results, right? Well, buckle up because I've got some juicy information for you. I've calculated the average execution times and meticulously compared them. Not stopping there, I've also kept an eye on memory allocation. Get ready to expand your knowledge with this priceless table that I've crafted, just for you. Feast your eyes on the valuable insights displayed below!

| Method                |        Mean |      Error |    StdDev |   Gen0 | Allocated |
| --------------------- | ----------: | ---------: | --------: | -----: | --------: |
| DontDoThis            | 5,476.47 ns | 102.899 ns | 96.252 ns | 1.2817 |    5368 B |
| JustPleaseDont        | 5,544.80 ns |  39.266 ns | 34.809 ns | 1.2817 |    5392 B |
| ValidRegexMatch       |   482.30 ns |   4.059 ns |  3.389 ns |      - |         - |
| InvalidRegexMatch     |   552.26 ns |   8.066 ns |  9.289 ns |      - |         - |
| ValidPatternMatch     |   374.81 ns |   4.567 ns |  4.048 ns |      - |         - |
| InvalidPatternMatch   |   545.98 ns |   7.518 ns |  6.665 ns |      - |         - |
| ValidGeneratedMatch   |    92.31 ns |   0.398 ns |  0.353 ns |      - |         - |
| InvalidGeneratedMatch |   109.59 ns |   0.650 ns |  0.608 ns |      - |         - |

So let's raise the roof for code generation! Woo hoo! It's an absolute game-changer, bringing in all the good vibes. The possibilities are endless, and I'm pumped up about it! Get ready to ride the wave of excitement, because code generation is where the party's at!
