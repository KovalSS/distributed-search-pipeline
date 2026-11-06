import os
import random
from locust import HttpUser, task, constant, events

@events.init_command_line_parser.add_listener
def init_parser(parser):
    parser.add_argument(
        "--mode", "-m",
        type=str,
        env_var="SEARCH_MODE",
        default="keyword",
        choices=["keyword", "expanded"],
        help="Search mode: 'keyword' (fast direct index lookup) or 'expanded' (AI Query Expansion via Ollama)"
    )

SAMPLE_QUERIES = [
    "scented candle",
    "essential oil",
    "laundry detergent",
    "aromatherapy diffuser",
    "hand soap",
    "organic shampoo",
    "air freshener",
    "massage oil",
    "soy candle",
    "paper towels",
    "cleaning spray",
    "vitamins supplement",
    "bath salts",
    "body wash",
    "herbal tea"
]

class SearchUser(HttpUser):
    host = "http://localhost:8080"
    wait_time = constant(0)

    def on_start(self):
        if hasattr(self.environment, "parsed_options") and self.environment.parsed_options and self.environment.parsed_options.mode:
            self.mode = self.environment.parsed_options.mode.lower()
        else:
            self.mode = os.environ.get("SEARCH_MODE", "keyword").lower()

    @task(10)
    def search_query(self):
        query = random.choice(SAMPLE_QUERIES)
        self.client.post(
            "/api/search",
            json={"query": query, "mode": self.mode, "top": 5},
            name=f"/api/search [{self.mode}]"
        )

    @task(1)
    def view_stats(self):
        self.client.get("/api/stats", name="/api/stats")

    @task(1)
    def check_health(self):
        self.client.get("/api/health", name="/api/health")
