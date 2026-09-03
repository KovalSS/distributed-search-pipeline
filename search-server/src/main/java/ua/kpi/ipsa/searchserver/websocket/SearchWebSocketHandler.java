package ua.kpi.ipsa.searchserver.websocket;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

import org.springframework.stereotype.Component;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import tools.jackson.databind.ObjectMapper;

import ua.kpi.ipsa.searchserver.index.SearchService;
import ua.kpi.ipsa.searchserver.ollama.OllamaClient;

@Component
public class SearchWebSocketHandler extends TextWebSocketHandler {

    private final OllamaClient ollamaClient;
    private final SearchService searchService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public SearchWebSocketHandler(OllamaClient ollamaClient, SearchService searchService) {
        this.ollamaClient = ollamaClient;
        this.searchService = searchService;
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        IncomingQuery incoming = objectMapper.readValue(message.getPayload(), IncomingQuery.class);
        String query = incoming.query();

        if (query == null || query.isBlank()) {
            sendJson(session, new ErrorMessage("error", "Query must not be empty"));
            return;
        }

        List<String> expandedTerms = ollamaClient.expandQuery(query);
        sendJson(session, new StageMessage("query_expansion",
                new QueryExpansionData(query, expandedTerms)));

        String fullQuery = query + " " + String.join(" ", expandedTerms);

        long start = System.currentTimeMillis();
        List<SearchService.ScoredDoc> results = searchService.keywordSearch(fullQuery, incoming.top());
        long elapsed = System.currentTimeMillis() - start;

        List<ResultItem> resultItems = results.stream()
                .map(doc -> new ResultItem(doc.docId(), doc.score(), doc.title()))
                .toList();
        sendJson(session, new StageMessage("keyword_search",
                new KeywordSearchData(resultItems, elapsed)));

        sendJson(session, new DoneMessage("done"));
    }

    private void sendJson(WebSocketSession session, Object payload) throws Exception {
        String json = objectMapper.writeValueAsString(payload);
        session.sendMessage(new TextMessage(json));
    }

    private record IncomingQuery(String query, Integer top) {
    }

    private record ErrorMessage(String stage, String message) {
    }

    private record StageMessage(String stage, Object data) {
    }

    private record QueryExpansionData(
            String original,
            @JsonProperty("expanded_terms") List<String> expandedTerms) {
    }

    private record ResultItem(@JsonProperty("doc_id") String docId, double score, String snippet) {
    }

    private record KeywordSearchData(
            List<ResultItem> results,
            @JsonProperty("time_ms") long timeMs) {
    }

    private record DoneMessage(String stage) {
    }
}
