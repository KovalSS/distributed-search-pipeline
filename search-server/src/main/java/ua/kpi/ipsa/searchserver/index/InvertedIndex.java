package ua.kpi.ipsa.searchserver.index;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class InvertedIndex {

    public record Posting(String docId, int termFrequency) {
    }

    private final CustomHashMap<String> index = new CustomHashMap<>();

    public void addDocument(String docId, String content) {
        Map<String, Integer> termCounts = countTerms(content);

        for (Map.Entry<String, Integer> entry : termCounts.entrySet()) {
            String term = entry.getKey();
            int frequency = entry.getValue();
            index.getOrCreate(term).add(new Posting(docId, frequency));
        }
    }

    public List<Posting> lookup(String term) {
        ConcurrentPostingList list = index.get(term.toLowerCase());
        if (list == null) {
            return List.of();
        }
        List<Posting> result = new ArrayList<>();
        for (Posting posting : list) {
            result.add(posting);
        }
        return result;
    }

    public int size() {
        return index.size();
    }

    private Map<String, Integer> countTerms(String content) {
        Map<String, Integer> counts = new java.util.HashMap<>();
        String[] words = content.toLowerCase().split("\\W+");

        for (String word : words) {
            if (word.isBlank()) {
                continue;
            }
            counts.merge(word, 1, Integer::sum);
        }
        return counts;
    }
}