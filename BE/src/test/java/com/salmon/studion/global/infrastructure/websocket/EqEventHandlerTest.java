// package com.salmon.studion.global.infrastructure.websocket;

// import com.fasterxml.jackson.databind.ObjectMapper;
// import com.salmon.studion.domain.eq.dto.TrackEqDraftState;
// import com.salmon.studion.domain.eq.dto.response.TrackEqLockResponse;
// import com.salmon.studion.domain.eq.service.TrackEqService;
// import com.salmon.studion.global.infrastructure.websocket.common.WsMessage;
// import com.salmon.studion.global.infrastructure.websocket.handler.EqEventHandler;
// import org.junit.jupiter.api.BeforeEach;
// import org.junit.jupiter.api.DisplayName;
// import org.junit.jupiter.api.Test;
// import org.junit.jupiter.api.extension.ExtendWith;
// import org.mockito.InjectMocks;
// import org.mockito.Mock;
// import org.mockito.Spy;
// import org.mockito.junit.jupiter.MockitoExtension;
// import org.springframework.web.socket.WebSocketSession;

// import java.net.URI;
// import java.util.List;
// import java.util.Map;

// import static org.mockito.ArgumentMatchers.any;
// import static org.mockito.ArgumentMatchers.eq;
// import static org.mockito.Mockito.lenient;
// import static org.mockito.Mockito.never;
// import static org.mockito.Mockito.verify;
// import static org.mockito.Mockito.when;

// @ExtendWith(MockitoExtension.class)
// class EqEventHandlerTest {

//     @Mock private WebSocketMessageSender webSocketMessageSender;
//     @Mock private TrackEqService trackEqService;
//     @Spy private ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();

//     @InjectMocks private EqEventHandler eqEventHandler;

//     @Mock private WebSocketSession session;

//     private static final Integer PROJECT_ID = 1;
//     private static final Integer USER_ID = 99;

//     @BeforeEach
//     void setUp() throws Exception {
//         lenient().when(session.getUri()).thenReturn(new URI("/ws/projects/" + PROJECT_ID));
//         lenient().when(session.getAttributes()).thenReturn(Map.of("userId", USER_ID));
//     }

//     @Test
//     @DisplayName("EQ_LOCK 이벤트는 전체 브로드캐스트한다")
//     void lockBroadcastsToAll() throws Exception {
//         TrackEqLockResponse response = TrackEqLockResponse.builder()
//                 .trackEqId(7)
//                 .isLocked(true)
//                 .userId(USER_ID)
//                 .build();
//         when(trackEqService.lockTrackEq(any(), eq(USER_ID))).thenReturn(response);

//         eqEventHandler.handleEqEvent(session, PROJECT_ID, "EQ_LOCK",
//                 wsMessage("EQ_LOCK", Map.of("projectId", PROJECT_ID, "trackEqId", 7, "isLocked", true)));

//         verify(webSocketMessageSender).broadcast(eq(PROJECT_ID), eq("EQ_LOCK"), eq(response));
//     }

//     @Test
//     @DisplayName("EQ_DRAFT_SAVE 이벤트는 draft 상태를 브로드캐스트한다")
//     void draftSaveBroadcastsToAll() throws Exception {
//         TrackEqDraftState response = TrackEqDraftState.builder()
//                 .projectId(PROJECT_ID)
//                 .trackEqId(7)
//                 .updatedBy(USER_ID)
//                 .version(1L)
//                 .bands(List.of())
//                 .build();
//         when(trackEqService.saveDraft(any(), eq(USER_ID))).thenReturn(response);

//         eqEventHandler.handleEqEvent(session, PROJECT_ID, "EQ_DRAFT_SAVE",
//                 wsMessage("EQ_DRAFT_SAVE", Map.of("projectId", PROJECT_ID, "trackEqId", 7, "bands", List.of())));

//         verify(webSocketMessageSender).broadcast(eq(PROJECT_ID), eq("EQ_DRAFT_SAVE"), eq(response));
//     }

//     @Test
//     @DisplayName("지원하지 않는 EQ 이벤트는 에러를 보낸다")
//     void invalidEventSendsError() throws Exception {
//         eqEventHandler.handleEqEvent(session, PROJECT_ID, "EQ_UNKNOWN", wsMessage("EQ_UNKNOWN", Map.of()));

//         verify(webSocketMessageSender).sendError(eq(session), eq(400), any(String.class));
//         verify(webSocketMessageSender, never()).broadcast(any(), any(), any());
//     }

//     private WsMessage<Map> wsMessage(String event, Map<String, Object> payload) {
//         WsMessage<Map> message = new WsMessage<>();
//         message.setEvent(event);
//         message.setPayload(payload);
//         return message;
//     }
// }
