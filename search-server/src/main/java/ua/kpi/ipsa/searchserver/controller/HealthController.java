package ua.kpi.ipsa.searchserver.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import ua.kpi.ipsa.searchserver.dto.HealthResponse;

@RestController
@RequestMapping("/api")
public class HealthController {

    @GetMapping("/health")
    public HealthResponse health() {
        boolean ollamaAvailable = false;
        return new HealthResponse("ok", ollamaAvailable);
    }
}