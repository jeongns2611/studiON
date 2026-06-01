package com.salmon.studion.global.config;

import com.salmon.studion.global.infrastructure.websocket.handler.ChatWebSocketHandler;
import com.salmon.studion.global.infrastructure.websocket.handler.ProjectWebSocketHandler;
import com.salmon.studion.global.infrastructure.websocket.interceptor.WebSocketHandshakeInterceptor;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

@Configuration
@EnableWebSocket
@RequiredArgsConstructor
public class WebSocketConfig implements WebSocketConfigurer {

    private final ProjectWebSocketHandler projectWebSocketHandler;
    private final WebSocketHandshakeInterceptor webSocketHandshakeInterceptor;
    private final ChatWebSocketHandler chatWebSocketHandler;

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(projectWebSocketHandler, "/ws/projects/{projectId}")
                .addInterceptors(webSocketHandshakeInterceptor)
                // 개발 환경
                .setAllowedOriginPatterns("*");
//                // 운영 환경
//                .setAllowedOrigins(
//                "http://localhost:3000",
//                "http://localhost:5173",
//                "https://studion.ai.kr");
        registry.addHandler(chatWebSocketHandler, "/ws/chat")
                // 개발 환경
                .setAllowedOriginPatterns("*");
//                // 운영 환경
//                .setAllowedOrigins(
//                "http://localhost:3000",
//                "http://localhost:5173",
//                "https://studion.ai.kr");
    }
}
