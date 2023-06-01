---
tags: ['paradigms', 'functional programming', 'csharp']
categories: ['programming', 'paradigms']
title: "What is functional programming?"
---

This is a very good question. Do you know? Because I don't. A lot of people say that it's awesome and much better than thinking about objects, but I never got a clear answer what it is exactly.

ChatGPT says it's:

>Functional programming is a programming paradigm that emphasizes the use of functions to solve problems. It is based on mathematical functions and is characterized by a focus on immutability, pure functions, and the use of higher-order functions. In functional programming, functions are first-class citizens, meaning they can be used as values and passed as arguments to other functions. The paradigm stresses on immutability, meaning that once a value is set, it cannot be changed, this makes it easier to reason about the code and eliminates the need for complex state management. Additionally, functional programming makes heavy use of higher-order functions, which are functions that take one or more functions as arguments and/or return a function as output. This allows for the creation of composable and reusable code. This paradigm is commonly used in functional languages such as Haskell, Lisp, and Scala but also can be found in modern JavaScript frameworks.

And that makes it completely clear right? It's not like after reading this I understand it even less. What does that even mean to be a *first-class citizen*? While learning other stuff about C# I heard tutors throw "functional programming" here and there while talking about some things that seem like they fit the definition, but I feel that they don't

## Is writing pure functions functional programming?

When learning about unit testing I learned that functional programming is all about writing pure functions inside your objects. That's great, and very useful to achieve easily testable code, but I don't think that simply avoiding putting state inside the class that performs the operation is enough.

```csharp
class Rectangle {
  public int width;
  public int height;
}

class PureFunctions {
    public static int CalculateArea(Rectangle r)
    {
        return r.width * r.height;
    }
}

Rectangle r1 = new Rectangle { width = 10, height = 20 };
Rectangle r2 = new Rectangle { width = 20, height = 20 };
int area1 = PureFunctions.CalculateArea(r1);
int area2 = PureFunctions.CalculateArea(r2);
Console.WriteLine(area1); // 200
Console.WriteLine(area2); // 400
```

## Is LINQ functional programming?

While checking out LINQ and reactive programming patterns I also heard words functional programming being thrown few times. There is no real state, and data is transformed with lambdas and they are functions, so is this functional programming?

```csharp
var people = new List<Person> {
    new Person { name = "John", age = 25 },
    new Person { name = "Jane", age = 35 },
    new Person { name = "Bob", age = 45 },
};

var names = people.Select(p => p.name);
```

Does this mean that every fluent API is in reality an implementation of functional programming paradigm?

## Is working with lambdas functional programming?

What if we go all it and simply write code with lambdas

```csharp
Func<int, int> Fibonacci = null;
Fibonacci = (n) => n > 1 ? Fibonacci(n - 1) + Fibonacci(n - 2) : n;

int fibonacciNumber = Fibonacci(10);
Console.WriteLine(fibonacciNumber); // 55
```

That definitely looks like it could be it, but the smell of that code prevents me from ever writing it in production. Even compiler doesn't like it. I had to put a concrete type `Func<int, int>` and I couldn't just use `var` because compiler couldn't infer it from context. That's not the way to go either.

## What is it then?

I asked ChatGPT one more time, and I got a pretty good answer:

>Functional programming in C# is a programming paradigm that emphasizes the use of functions to solve problems, and it's based on the principles of functional programming, but adapted to the C# language. C# has been evolving over the years to include more functional programming features such as lambda expressions, Linq and more.
>
>Functional programming in C# is characterized by:
>
>- The use of immutable data, this means that once a variable is set, it cannot be changed
>- The use of pure functions, functions that have no side effects and always return the same output for a given input
>- The use of higher-order functions, functions that take one or more functions as arguments and/or return a function as output
>- The use of recursion, instead of using loops or iterative statements
>- The use of lambda expressions, anonymous functions that can be passed as arguments to other functions
>- The use of Linq, a set of extension methods that enable querying and manipulating collections of data in a functional way
>
>Functional programming in C# allows developers to write more expressive, composable, and testable code. It's not a replacement for the object-oriented paradigm, but it's a way to use some of the functional programming concepts and techniques to improve the code quality.

There is no **real** functional programming in C#. I guess that's what F# is for. But the spirit of functional programming is there, and it can help to write cleaner, and easily testable code. I know that learning all this made me think about changing the way I code.
