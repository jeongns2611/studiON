// // package com.salmon.studion.global.infrastructure.websocket;

// import com.fasterxml.jackson.databind.ObjectMapper;
// import com.salmon.studion.domain.clip.dto.response.ClipCopyResponse;
// import com.salmon.studion.domain.clip.dto.response.ClipCreateResponse;
// import com.salmon.studion.domain.clip.dto.response.ClipMoveResponse;
// import com.salmon.studion.domain.clip.service.ClipService;
// import com.salmon.studion.global.infrastructure.websocket.common.WsMessage;
// import com.salmon.studion.global.infrastructure.websocket.handler.ClipEventHandler;
// import com.salmon.studion.global.scheduler.ProjectAutosaveScheduler;
// import org.junit.jupiter.api.BeforeEach;
// import org.junit.jupiter.api.DisplayName;
// import org.junit.jupiter.api.Nested;
// import org.junit.jupiter.api.Test;
// import org.junit.jupiter.api.extension.ExtendWith;
// import org.mockito.InjectMocks;
// import org.mockito.Mock;
// import org.mockito.Spy;
// import org.mockito.junit.jupiter.MockitoExtension;
// import org.springframework.web.socket.WebSocketSession;

// import java.net.URI;
// import java.util.Map;

// import static org.mockito.ArgumentMatchers.*;
// import static org.mockito.Mockito.*;

// @ExtendWith(MockitoExtension.class)
// class ClipEventHandlerTest {

    // @Mock private WebSocketMessageSender webSocketMessageSender;
    // @Mock private ClipService clipService;
    // @Mock private ProjectAutosaveScheduler projectAutosaveScheduler;
    // @Spy  private ObjectMapper objectMapper = new ObjectMapper();

//     @InjectMocks private ClipEventHandler clipEventHandler;

//     @Mock private WebSocketSession session;

//     private static final Integer PROJECT_ID = 1;
//     private static final Integer USER_ID = 0;

//     @BeforeEach
//     void setUp() throws Exception {
//         lenient().when(session.getUri()).thenReturn(new URI("/ws/projects/" + PROJECT_ID));
//         lenient().when(session.getAttributes()).thenReturn(Map.of("userId", USER_ID));
//     }

//     private WsMessage<Map> wsMessage(String event, Map<String, Object> payload) {
//         WsMessage<Map> msg = new WsMessage<>();
//         msg.setEvent(event);
//         msg.setPayload(payload);
//         return msg;
//     }

//     @Nested
//     @DisplayName("CLIP_CREATE")
//     class CreateTest {

//         @Test
//         @DisplayName("CREATE 성공 시 전체 브로드캐스트로 응답을 전송한다")
//         void createBroadcastsToAll() throws Exception {
//             ClipCreateResponse response = ClipCreateResponse.builder()
//                     .clipId(10).trackId(2).startBar(0.0).duration(4.0)
//                     .color("#FF0000").audioMetadataId(42).audioStartMs(0).audioDurationMs(8000)
//                     .build();
//             when(clipService.createClip(any(), eq(USER_ID))).thenReturn(response);

//             clipEventHandler.handleClipEvent(session, PROJECT_ID, "CLIP_CREATE",
//                     wsMessage("CLIP_CREATE", Map.of(
//                             "projectId", PROJECT_ID,
//                             "trackId", 2,
//                             "startBar", 0.0,
//                             "color", "#FF0000",
//                             "objectKey", "projects/1/audios/test.mp3",
//                             "originalName", "test.mp3",
//                             "storedName", "test.mp3",
//                             "mimeType", "MPEG",
//                             "sizeBytes", 100000,
//                             "durationMs", 8000
//                     )));

//             verify(webSocketMessageSender).broadcast(eq(PROJECT_ID), eq("CLIP_CREATE"), eq(response));
//             verify(webSocketMessageSender, never()).sendToSession(any(), any(), any());
//         }
//     }

//     @Nested
//     @DisplayName("CLIP_COPY")
//     class CopyTest {

//         @Test
//         @DisplayName("COPY 성공 시 broadcast가 아닌 요청 세션에만 응답을 전송한다")
//         void copySendsToSessionOnly() throws Exception {
//             ClipCopyResponse response = ClipCopyResponse.builder().clipId(3).build();
//             when(clipService.copyClip(any(), eq(USER_ID))).thenReturn(response);

//             clipEventHandler.handleClipEvent(session, PROJECT_ID, "CLIP_COPY",
//                     wsMessage("CLIP_COPY", Map.of("projectId", PROJECT_ID, "clipId", 3)));

//             verify(webSocketMessageSender).sendToSession(eq(session), eq("CLIP_COPY"), eq(response));
//             verify(webSocketMessageSender, never()).broadcast(any(), any(), any());
//         }
//     }

//     @Nested
//     @DisplayName("CLIP_MOVE")
//     class MoveTest {

//         @Test
//         @DisplayName("MOVE 성공 시 전체 브로드캐스트로 응답을 전송한다")
//         void moveBroadcastsToAll() throws Exception {
//             ClipMoveResponse response = ClipMoveResponse.builder()
//                     .clipId(3)
//                     .before(ClipMoveResponse.ClipPosition.builder().trackId(1).startBar(1.0).build())
//                     .after(ClipMoveResponse.ClipPosition.builder().trackId(2).startBar(4.0).build())
//                     .build();
//             when(clipService.moveClip(any(), eq(USER_ID))).thenReturn(response);

//             clipEventHandler.handleClipEvent(session, PROJECT_ID, "CLIP_MOVE",
//                     wsMessage("CLIP_MOVE", Map.of("projectId", PROJECT_ID, "clipId", 3,
//                             "targetTrackId", 2, "targetStartBar", 4.0)));

//             verify(webSocketMessageSender).broadcast(eq(PROJECT_ID), eq("CLIP_MOVE"), eq(response));
//             verify(webSocketMessageSender, never()).sendToSession(any(), any(), any());
//         }
//     }
// }
