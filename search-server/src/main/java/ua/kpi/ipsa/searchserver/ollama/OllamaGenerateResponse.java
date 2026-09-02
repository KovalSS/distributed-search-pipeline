package ua.kpi.ipsa.searchserver.ollama;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record OllamaGenerateResponse(String response) {
}