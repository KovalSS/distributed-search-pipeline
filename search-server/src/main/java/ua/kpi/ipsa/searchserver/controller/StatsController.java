package ua.kpi.ipsa.searchserver.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import ua.kpi.ipsa.searchserver.dto.StatsResponse;
import ua.kpi.ipsa.searchserver.index.IndexingService;

@RestController
@RequestMapping("/api")
public class StatsController {

    private final IndexingService indexingService;

    public StatsController(IndexingService indexingService) {
        this.indexingService = indexingService;
    }

    @GetMapping("/stats")
    public StatsResponse stats() {
        return new StatsResponse(
                indexingService.getDocumentsIndexed(),
                indexingService.getLastBuildTimeMs(),
                indexingService.getLastThreadsUsed()
        );
    }
}