---
tags: ["ai", "embeddings"]
categories: ["ai", "embeddings"]
title: "Playing with AI: How to talk to your SQL database"
image:
  path: /assets/img/2024-06-30/database.jpg
  alt: Talking to your database!
---
I'm little late to the AI hype and needing to catch up. Fortunately the company I work for recently organized an internal AI themed hackathon. I hijacked the opportunity and started learning abut different models. I still have almost no idea what I'm doing, but this is my latest weekend project.

By spending a day on hacking together a simple RAG chatbot with personality I learned, among other things, about vector databases. This gave me an idea for a product that could actually be useful. This is a simple experiment showing how a customer could safely talk to a database without a risk of SQL injection.

To make things simple I used [Google Colaboratory](https://colab.research.google.com/) because installing dependencies is boring. All code below should run fine on a free "CPU" runtime. Thanks to Google it's enough to install just those three libraries. So make a code block like this, and run it.

```python
!pip install sentence-transformers --quiet

!pip install faiss-cpu --quiet
!pip install datasets --quiet
```

Now let's do the necessary python imports

```python
from sentence_transformers import SentenceTransformer
from datasets import Dataset
```

It's time to download a Sentence transformer from "Hugging Face" with this sexy line of code. This transformer can be used to convert any string to a vector in 1024 dimensional space. This is a complex way of saying it's just an array of 1024 integers.

```python
encoder = SentenceTransformer("mixedbread-ai/mxbai-embed-large-v1")
```

Now comes the boring manual part. I had to prepare the data for the database. I'm lazy so I asked ChatGPT to prepare me 30 random SQL queries, with short descriptions, that should work with AdventureWorks sample database. Resulting list is far to long to put it here, but here is a tiny part of it.

```python
data = [
  {
    'text': 'Retrieve all columns from the Product table',
    'sql': 'SELECT * FROM Production.Product;'
  },
  {
    'text': 'Get the first name and last name of all employees',
    'sql': 'SELECT FirstName, LastName FROM HumanResources.Employee;'
    },
  {
    'text': 'List all product names and their standard costs',
    'sql': 'SELECT Name, StandardCost FROM Production.Product;'
  },
  {
    'text': 'Count the number of employees',
    'sql': 'SELECT COUNT(*) AS NumberOfEmployees FROM HumanResources.Employee'
  },
  {
    'text': 'Find all orders with a subtotal greater than $1000',
    'sql': 'SELECT * FROM Sales.SalesOrderHeader WHERE SubTotal > 1000;'
  },
  {
    'text': 'Find products that have "Bike" in their name',
    'sql': 'SELECT * FROM Production.Product WHERE Name LIKE \'%Bike%\';'
  },
]
```

Now we use the power of Python and prepare an in memory vector database. We put descriptions in column `text`, queries in column `sql` and vectors in column `embeddings`. This is just a simplest possible example. If you want to make it better make 10 different descriptions of every query and make embeddings to every one of them. More vectors will make better search results.

```python
dataset = Dataset.from_dict({
  'text' : [d['text'] for d in data],
  'sql' : [d['sql'] for d in data],
  'embeddings' : [encoder.encode(d['text']) for d in data],
});
```

Every database needs an index to retrieve results faster. This is an index dedicated for n-dimensional vectors.

```python
dataset.add_faiss_index(column='embeddings')
```

And we are done! Now we can search through the database. Let's start with a request coming straight from the customer! Someone wants to `show expensive orders`. If we searched through the strings directly we would have hard time finding what customer wanted, because nowhere in the queries of descriptions we can find the word `expensive`. But fortunately `mixedbread-ai/mxbai-embed-large-v1` knows exactly what it means.

```python
# Calculate a vector of what customer requested.
search = encoder.encode('show expensive orders')

# Look into the database for one vector closest to the `search` vector.
scores, retrieved = dataset.get_nearest_examples("embeddings", query, 1)

# Print stuff out
print(scores)
print(retrieved["text"])
print(retrieved["sql"])
```

What we see in the console is awesome!

```console
[139.02415]
['Find all orders with a subtotal greater than $1000']
['SELECT * FROM Sales.SalesOrderHeader WHERE SubTotal > 1000;']
```

I barely did anything and I have a SQL query that I can now use to generate a report for the customer. There was no opportunity to inject anything into the query parameters. Even if the model is malicious it still can't do anything to mess this up! It's useful and safe.

What is displayed when we ask this database to `show employes`?

```console
[172.91516]
['Get the first name and last name of all employees']
['SELECT FirstName, LastName FROM HumanResources.Employee;']
```

AI will take our jobs!

But what if we ask it about something that it doesn't know! Like `What was the movie where J.Lo fell in love with an AI?` the answer is of course "Atlas" released in 2024, but I would also accept answer "Titanfall the Movie" What our database thinks about it?

```console
[416.46304]
['Find products that have "Bike" in their name']
["SELECT * FROM Production.Product WHERE Name LIKE '%Bike%';"]
```

Oh, that's not the right answer!

It found the nearest vector, but it was still pretty far away. The `score` was `416.46304` which is over two times larger than scores of two other answers. That's actually great, because we have a simple way to detect if our database doesn't contain an answer, and when to simply reply "I have no idea".
