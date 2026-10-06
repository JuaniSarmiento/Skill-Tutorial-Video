llamadas = {"total": 0}


def fibonacci(n):
    llamadas["total"] += 1
    if n == 0 or n == 1:
        return n
    else:
        return fibonacci(n - 1) + fibonacci(n - 2)


for n in [5, 10, 20, 25, 30]:
    llamadas["total"] = 0
    resultado = fibonacci(n)
    print(f"fibonacci({n}) = {resultado} -> {llamadas['total']} llamadas")
