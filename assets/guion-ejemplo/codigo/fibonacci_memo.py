memo = {}


def fibonacci_memo(n):
    if n in memo:
        return memo[n]
    if n <= 1:
        memo[n] = n
    else:
        memo[n] = fibonacci_memo(n - 1) + fibonacci_memo(n - 2)
    return memo[n]


print(fibonacci_memo(6))    # 8
print(fibonacci_memo(100))  # 354224848179261915075
