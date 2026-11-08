package ua.kpi.ipsa.searchserver.controller;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import ua.kpi.ipsa.searchserver.dto.IndexRequest;
import ua.kpi.ipsa.searchserver.dto.IndexResponse;
import ua.kpi.ipsa.searchserver.index.IndexingService;

@RestController
@RequestMapping("/api")
public class IndexController {

    private final IndexingService indexingService;

    public IndexController(IndexingService indexingService) {
        this.indexingService = indexingService;
    }

    @PostMapping("/index")
    public IndexResponse index(@RequestBody(required = false) IndexRequest request) {
        int threads = (request == null || request.threads() == null || request.threads() <= 0)
                ? Runtime.getRuntime().availableProcessors()
                : request.threads();
        IndexingService.IndexResult result = indexingService.buildIndex(threads);
        return new IndexResponse("ok", result.documentsIndexed(), result.timeMs());
    }
}
