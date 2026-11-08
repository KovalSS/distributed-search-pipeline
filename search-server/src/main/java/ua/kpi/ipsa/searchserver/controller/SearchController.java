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
import ua.kpi.ipsa.searchserver.ollama.OllamaClient;

@RestController
@RequestMapping("/api")
public class SearchController {

    private final SearchService searchService;
    private final OllamaClient ollamaClient;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public SearchController(SearchService searchService, OllamaClient ollamaClient) {
        this.searchService = searchService;
        this.ollamaClient = ollamaClient;
    }

    @PostMapping("/search")
    public SearchResponse search(@RequestBody SearchRequest request) {
        if (request.query() == null || request.query().isBlank()) {
            return new SearchResponse(List.of(), 0);
        }

        List<String> synonyms = null;
        String queryToSearch = request.query();

        if ("expanded".equalsIgnoreCase(request.mode())) {
            synonyms = ollamaClient.expandQuery(request.query());
            if (synonyms != null && !synonyms.isEmpty()) {
                queryToSearch = request.query() + " " + String.join(" ", synonyms);
            }
        }

        long start = System.currentTimeMillis();
        List<SearchService.ScoredDoc> scored = searchService.keywordSearch(queryToSearch, request.top());
        long elapsed = System.currentTimeMillis() - start;

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

        return new SearchResponse(results, elapsed, synonyms);
    }
}
