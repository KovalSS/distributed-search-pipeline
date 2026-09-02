package ua.kpi.ipsa.searchserver.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import ua.kpi.ipsa.searchserver.dto.HealthResponse;
import ua.kpi.ipsa.searchserver.ollama.OllamaClient;

@RestController
@RequestMapping("/api")
public class HealthController {

    private final OllamaClient ollamaClient;

    public HealthController(OllamaClient ollamaClient) {
        this.ollamaClient = ollamaClient;
    }

    @GetMapping("/health")
    public HealthResponse health() {
        boolean ollamaAvailable = ollamaClient.isAvailable();
        return new HealthResponse("ok", ollamaAvailable);
    }
}