package ua.kpi.ipsa.searchserver.websocket;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private final SearchWebSocketHandler searchWebSocketHandler;

    public WebSocketConfig(SearchWebSocketHandler searchWebSocketHandler) {
        this.searchWebSocketHandler = searchWebSocketHandler;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(searchWebSocketHandler, "/ws/search")
                .setAllowedOrigins("*");
    }
}