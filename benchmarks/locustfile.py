import random
from locust import HttpUser, task, constant

SAMPLE_QUERIES = [
    "wireless mouse",
    "gaming laptop",
    "mechanical keyboard",
    "bluetooth headphones",
    "usb c hub",
    "hdmi cable",
    "fast charger",
    "external ssd",
    "laptop stand",
    "protective case",
    "ergonomic chair",
    "portable monitor",
    "wireless earbuds",
    "power bank"
]

class SearchUser(HttpUser):
    host = "http://localhost:8080"
    wait_time = constant(0)

    @task(10)
    def search_keyword(self):
        query = random.choice(SAMPLE_QUERIES)
        self.client.post(
            "/api/search",
            json={"query": query, "top": 5},
            name="/api/search [keyword]"
        )

    @task(1)
    def view_stats(self):
        self.client.get("/api/stats", name="/api/stats")

    @task(1)
    def check_health(self):
        self.client.get("/api/health", name="/api/health")
