package com.salmon.studion.global.infrastructure.websocket.common;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class WsMessage<T> {
    private String event;
    private T payload;
}
