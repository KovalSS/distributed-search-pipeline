package ua.kpi.ipsa.searchserver.index;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Service;

@Service
public class SearchService {

    private static final int DEFAULT_RESULTS = 5;
    private static final int MAX_RESULTS = 100;

    private final IndexingService indexingService;

    public SearchService(IndexingService indexingService) {
        this.indexingService = indexingService;
    }

    public List<ScoredDoc> keywordSearch(String query) {
        return keywordSearch(query, null);
    }

    public List<ScoredDoc> keywordSearch(String query, Integer requestedTop) {
        int limit = (requestedTop == null || requestedTop <= 0)
                ? DEFAULT_RESULTS
                : Math.min(requestedTop, MAX_RESULTS);

        InvertedIndex index = indexingService.getIndex();

        String[] terms = query.toLowerCase().split("\\W+");
        Map<String, Double> scores = new HashMap<>();

        for (String term : terms) {
            if (term.isBlank()) {
                continue;
            }
            List<InvertedIndex.Posting> postings = index.lookup(term);
            for (InvertedIndex.Posting posting : postings) {
                scores.merge(posting.docId(), (double) posting.termFrequency(), Double::sum);
            }
        }

        List<ScoredDoc> results = new ArrayList<>();
        for (Map.Entry<String, Double> entry : scores.entrySet()) {
            String docId = entry.getKey();
            results.add(new ScoredDoc(docId, entry.getValue(), indexingService.getTitle(docId)));
        }

        results.sort((a, b) -> Double.compare(b.score(), a.score()));

        if (results.size() > limit) {
            return results.subList(0, limit);
        }
        return results;
    }

    public record ScoredDoc(String docId, double score, String title) {
    }
}