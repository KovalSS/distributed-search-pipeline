package ua.kpi.ipsa.searchserver.controller;

import java.util.ArrayList;
import java.util.List;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import ua.kpi.ipsa.searchserver.dto.SearchRequest;
import ua.kpi.ipsa.searchserver.dto.SearchResponse;
import ua.kpi.ipsa.searchserver.index.SearchService;

@RestController
@RequestMapping("/api")
public class SearchController {

    private final SearchService searchService;

    public SearchController(SearchService searchService) {
        this.searchService = searchService;
    }

    @PostMapping("/search")
    public SearchResponse search(@RequestBody SearchRequest request) {
        long start = System.currentTimeMillis();

        List<SearchService.ScoredDoc> scored = searchService.keywordSearch(request.query());

        List<SearchResponse.SearchResult> results = new ArrayList<>();
        for (SearchService.ScoredDoc doc : scored) {
            results.add(new SearchResponse.SearchResult(doc.docId(), doc.score(), ""));
        }

        long elapsed = System.currentTimeMillis() - start;
        return new SearchResponse(results, elapsed);
    }
}