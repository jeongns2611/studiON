package com.salmon.studion.global.infrastructure.websocket.common;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public class WsErrorResponse {
    private int code;
    private String message;
}
