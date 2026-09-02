package ua.kpi.ipsa.searchserver.ollama;

public record OllamaGenerateRequest(String model, String prompt, boolean stream) {
}