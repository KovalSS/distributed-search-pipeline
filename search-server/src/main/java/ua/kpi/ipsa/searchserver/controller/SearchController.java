package ua.kpi.ipsa.searchserver.controller;

import java.util.ArrayList;
import java.util.List;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import tools.jackson.databind.ObjectMapper;

import ua.kpi.ipsa.searchserver.dto.SearchRequest;
import ua.kpi.ipsa.searchserver.dto.SearchResponse;
import ua.kpi.ipsa.searchserver.index.SearchService;

@RestController
@RequestMapping("/api")
public class SearchController {

    private final SearchService searchService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public SearchController(SearchService searchService) {
        this.searchService = searchService;
    }

    @PostMapping("/search")
    public SearchResponse search(@RequestBody SearchRequest request) {
        if (request.query() == null || request.query().isBlank()) {
            return new SearchResponse(List.of(), 0);
        }

        long start = System.currentTimeMillis();

        List<SearchService.ScoredDoc> scored = searchService.keywordSearch(request.query(), request.top());

        List<SearchResponse.SearchResult> results = new ArrayList<>();
        for (SearchService.ScoredDoc doc : scored) {
            String rawJson = searchService.getDocumentJson(doc.docId());
            Object rawObj = null;
            if (rawJson != null) {
                try {
                    rawObj = objectMapper.readTree(rawJson);
                } catch (Exception ignored) {
                }
            }
            results.add(new SearchResponse.SearchResult(doc.docId(), doc.score(), doc.title(), rawObj));
        }

        long elapsed = System.currentTimeMillis() - start;
        return new SearchResponse(results, elapsed);
    }
}
