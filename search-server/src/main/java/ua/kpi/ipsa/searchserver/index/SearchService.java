package ua.kpi.ipsa.searchserver.index;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Service;

@Service
public class SearchService {

    private final IndexingService indexingService;

    public SearchService(IndexingService indexingService) {
        this.indexingService = indexingService;
    }

    public List<ScoredDoc> keywordSearch(String query) {
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
            results.add(new ScoredDoc(entry.getKey(), entry.getValue()));
        }

        results.sort((a, b) -> Double.compare(b.score(), a.score()));

        return results;
    }

    public record ScoredDoc(String docId, double score) {
    }
}