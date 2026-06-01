// // package com.salmon.studion.domain.track.service;
//
// // import com.fasterxml.jackson.core.JsonProcessingException;
// // import com.fasterxml.jackson.databind.ObjectMapper;
// // import com.salmon.studion.domain.clip.service.ClipService;
// // import com.salmon.studion.domain.eq.service.TrackEqService;
// // import com.salmon.studion.domain.project.entity.Project;
// // import com.salmon.studion.domain.project.service.ProjectService;
// // import com.salmon.studion.domain.track.dto.TrackState;
// // import com.salmon.studion.domain.track.dto.request.TrackAddRequest;
// // import com.salmon.studion.domain.track.dto.request.TrackRemoveRequest;
// // import com.salmon.studion.domain.track.dto.request.TrackRenameRequest;
// // import com.salmon.studion.domain.track.dto.request.TrackReorderRequest;
// // import com.salmon.studion.domain.track.dto.request.TrackMuteRequest;
// // import com.salmon.studion.domain.track.dto.request.TrackPanRequest;
// // import com.salmon.studion.domain.track.dto.request.TrackVolumeRequest;
// // import com.salmon.studion.domain.track.dto.request.TrackSoloRequest;
// // import com.salmon.studion.domain.track.dto.response.TrackAddResponse;
// // import com.salmon.studion.domain.track.dto.response.TrackRemoveResponse;
// // import com.salmon.studion.domain.track.dto.response.TrackRenameResponse;
// // import com.salmon.studion.domain.track.dto.response.TrackReorderResponse;
// // import com.salmon.studion.domain.track.dto.response.TrackMuteResponse;
// // import com.salmon.studion.domain.track.dto.response.TrackPanResponse;
// // import com.salmon.studion.domain.track.dto.response.TrackVolumeResponse;
// // import com.salmon.studion.domain.track.dto.response.TrackSoloResponse;
// // import com.salmon.studion.global.exception.BusinessException;
// // import org.junit.jupiter.api.BeforeEach;
// // import org.junit.jupiter.api.DisplayName;
// // import org.junit.jupiter.api.Nested;
// // import org.junit.jupiter.api.Test;
// // import org.junit.jupiter.api.extension.ExtendWith;
// // import org.mockito.InjectMocks;
// // import org.mockito.Mock;
// // import org.mockito.Spy;
// // import org.mockito.junit.jupiter.MockitoExtension;
// // import org.springframework.data.redis.core.HashOperations;
// // import org.springframework.data.redis.core.RedisTemplate;
// // import org.springframework.data.redis.core.SetOperations;
// // import org.springframework.data.redis.core.ValueOperations;
//
// // import java.util.HashMap;
// // import java.util.Map;
//
// import com.salmon.studion.global.common.response.ErrorCode;
// import static org.assertj.core.api.Assertions.assertThat;
// import static org.assertj.core.api.Assertions.assertThatThrownBy;
// import static org.mockito.ArgumentMatchers.*;
// import static org.mockito.Mockito.*;
//
// // @ExtendWith(MockitoExtension.class)
// // class TrackServiceTest {
//
// //     @Mock private ProjectService projectService;
// //     @Mock private ClipService clipService;
// //     @Mock private TrackEqService trackEqService;
// //     @Mock private RedisTemplate<String, String> redisTemplate;
// //     @Mock private com.salmon.studion.domain.track.repository.TrackRepository trackRepository;
// //     @Mock private com.salmon.studion.domain.track.repository.TrackEventRepository trackEventRepository;
// //     @Spy  private ObjectMapper objectMapper = new ObjectMapper();
//
// //     @InjectMocks private TrackService trackService;
//
// //     @Mock private ValueOperations<String, String> valueOperations;
// //     @Mock private HashOperations<String, Object, Object> hashOperations;
// //     @Mock private SetOperations<String, String> setOperations;
//
// //     private static final Integer PROJECT_ID = 1;
// //     private static final String TRACKS_KEY = "project:1:tracks";
// //     private static final String TRACK_ID_SEQ_KEY = "global:track:id_seq";
// //     private static final String EVENT_SEQ_KEY = "project:1:event:seq";
//
// //     private Map<String, String> store;
//
// //     @BeforeEach
// //     void setUp() {
// //         store = new HashMap<>();
//
// //         lenient().when(redisTemplate.opsForValue()).thenReturn(valueOperations);
// //         lenient().when(redisTemplate.opsForHash()).thenReturn(hashOperations);
// //         lenient().when(redisTemplate.opsForSet()).thenReturn(setOperations);
// //         lenient().when(projectService.getProjectOrThrow(PROJECT_ID)).thenReturn(mock(Project.class));
//
// //         lenient().doAnswer(inv -> store.get(inv.getArgument(1).toString()))
// //                 .when(hashOperations).get(eq(TRACKS_KEY), any());
//
// //         lenient().doAnswer(inv -> {
// //             store.put(inv.getArgument(1).toString(), inv.getArgument(2).toString());
// //             return null;
// //         }).when(hashOperations).put(eq(TRACKS_KEY), any(), any());
//
// //         lenient().doAnswer(inv -> new HashMap<>(store))
// //                 .when(hashOperations).entries(eq(TRACKS_KEY));
// //     }
//
// //     private String trackJson(Integer trackId, Integer pre, Integer post) throws JsonProcessingException {
// //         return objectMapper.writeValueAsString(TrackState.builder()
// //                 .trackId(trackId).name("track" + trackId).type("audio")
// //                 .preTrackId(pre).postTrackId(post)
// //                 .isMuted(false).isSoloed(false).volume(0.0).pan(0)
// //                 .build());
// //     }
//
// //     private TrackState fromStore(Integer trackId) throws JsonProcessingException {
// //         return objectMapper.readValue(store.get(String.valueOf(trackId)), TrackState.class);
// //     }
//
// //     private TrackAddRequest addRequest(String name, String type) {
// //         TrackAddRequest req = new TrackAddRequest();
// //         req.setProjectId(PROJECT_ID);
// //         req.setName(name);
// //         req.setType(type);
// //         return req;
// //     }
//
// //     private TrackRemoveRequest removeRequest(Integer trackId) {
// //         TrackRemoveRequest req = new TrackRemoveRequest();
// //         req.setProjectId(PROJECT_ID);
// //         req.setTrackId(trackId);
// //         return req;
// //     }
//
//     private TrackReorderRequest reorderRequest(Integer trackId, Integer targetPre, Integer targetPost) {
//         TrackReorderRequest req = new TrackReorderRequest();
//         req.setProjectId(PROJECT_ID);
//         req.setTrackId(trackId);
//         req.setPreTrackId(targetPre);
//         req.setPostTrackId(targetPost);
//         return req;
//     }
//
// //     private TrackRenameRequest renameRequest(Integer trackId, String name) {
// //         TrackRenameRequest req = new TrackRenameRequest();
// //         req.setProjectId(PROJECT_ID);
// //         req.setTrackId(trackId);
// //         req.setName(name);
// //         return req;
// //     }
//
// //     private TrackSoloRequest soloRequest(Integer trackId, Boolean isSoloed) {
// //         TrackSoloRequest req = new TrackSoloRequest();
// //         req.setProjectId(PROJECT_ID);
// //         req.setTrackId(trackId);
// //         req.setIsSoloed(isSoloed);
// //         return req;
// //     }
//
// //     private TrackMuteRequest muteRequest(Integer trackId, Boolean isMuted) {
// //         TrackMuteRequest req = new TrackMuteRequest();
// //         req.setProjectId(PROJECT_ID);
// //         req.setTrackId(trackId);
// //         req.setIsMuted(isMuted);
// //         return req;
// //     }
//
// //     private TrackVolumeRequest volumeRequest(Integer trackId, Double volume) {
// //         TrackVolumeRequest req = new TrackVolumeRequest();
// //         req.setProjectId(PROJECT_ID);
// //         req.setTrackId(trackId);
// //         req.setVolume(volume);
// //         return req;
// //     }
//
// //     private TrackPanRequest panRequest(Integer trackId, Integer pan) {
// //         TrackPanRequest req = new TrackPanRequest();
// //         req.setProjectId(PROJECT_ID);
// //         req.setTrackId(trackId);
// //         req.setPan(pan);
// //         return req;
// //     }
//
// //     @Nested
// //     @DisplayName("전역 시퀀스")
// //     class GlobalSequenceTest {
//
// //         @Test
// //         @DisplayName("서로 다른 프로젝트의 트랙 추가는 동일한 전역 시퀀스 키를 사용한다")
// //         void differentProjectsUseSameGlobalKey() {
// //             Integer projectId2 = 2;
// //             lenient().when(projectService.getProjectOrThrow(projectId2)).thenReturn(mock(Project.class));
//
// //             String tracks2Key = "project:2:tracks";
// //             lenient().doAnswer(inv -> null)
// //                     .when(hashOperations).get(eq(tracks2Key), any());
// //             lenient().doAnswer(inv -> new HashMap<>())
// //                     .when(hashOperations).entries(eq(tracks2Key));
//
// //             when(valueOperations.increment(TRACK_ID_SEQ_KEY)).thenReturn(1L).thenReturn(2L);
// //             when(valueOperations.increment("project:1:event:seq")).thenReturn(1L);
// //             when(valueOperations.increment("project:2:event:seq")).thenReturn(1L);
//
// //             TrackAddRequest req1 = addRequest("track1", "audio");
// //             TrackAddRequest req2 = addRequest("track1", "audio");
// //             req2.setProjectId(projectId2);
//
// //             trackService.addTrack(req1, 0);
// //             trackService.addTrack(req2, 0);
//
// //             verify(valueOperations, times(2)).increment(TRACK_ID_SEQ_KEY);
// //             verify(valueOperations, never()).increment("project:1:track:id_seq");
// //             verify(valueOperations, never()).increment("project:2:track:id_seq");
// //         }
// //     }
//
// //     @Nested
// //     @DisplayName("addTrack")
// //     class AddTrackTest {
//
// //         @Test
// //         @DisplayName("빈 프로젝트에 첫 트랙 추가 시 preTrackId가 null이다")
// //         void addFirstTrack() throws JsonProcessingException {
// //             when(valueOperations.increment(TRACK_ID_SEQ_KEY)).thenReturn(1L);
// //             when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);
//
// //             TrackAddResponse response = trackService.addTrack(addRequest("track1", "audio"), 0);
//
// //             assertThat(response.getTrackId()).isEqualTo(1);
// //             assertThat(response.getPreTrackId()).isNull();
// //             assertThat(response.getPostTrackId()).isNull();
//
// //             TrackState saved = fromStore(1);
// //             assertThat(saved.getPreTrackId()).isNull();
// //             assertThat(saved.getPostTrackId()).isNull();
// //         }
//
// //         @Test
// //         @DisplayName("기존 트랙 있을 때 추가 시 마지막 트랙의 postTrackId가 새 트랙으로 업데이트된다")
// //         void addTrackAfterExisting() throws JsonProcessingException {
// //             store.put("1", trackJson(1, null, null));
//
// //             when(valueOperations.increment(TRACK_ID_SEQ_KEY)).thenReturn(2L);
// //             when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(2L);
//
// //             TrackAddResponse response = trackService.addTrack(addRequest("track2", "audio"), 0);
//
// //             assertThat(response.getTrackId()).isEqualTo(2);
// //             assertThat(response.getPreTrackId()).isEqualTo(1);
// //             assertThat(response.getPostTrackId()).isNull();
//
//             assertThat(fromStore(1).getPostTrackId()).isEqualTo(2);
//             assertThat(fromStore(2).getPreTrackId()).isEqualTo(1);
//         }
//
//         @Test
//         @DisplayName("트랙 수가 50개에 도달하면 TRACK_LIMIT_EXCEEDED 예외를 던진다")
//         void addTrack_limitExceeded() {
//             when(hashOperations.size(TRACKS_KEY)).thenReturn(50L);
//
//             assertThatThrownBy(() -> trackService.addTrack(addRequest("track51", "audio"), 0))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.TRACK_LIMIT_EXCEEDED));
//         }
//
//         @Test
//         @DisplayName("트랙 수가 49개이면 정상적으로 추가된다")
//         void addTrack_underLimit() throws JsonProcessingException {
//             when(hashOperations.size(TRACKS_KEY)).thenReturn(49L);
//             when(valueOperations.increment(TRACK_ID_SEQ_KEY)).thenReturn(50L);
//             when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);
//
//             TrackAddResponse response = trackService.addTrack(addRequest("track50", "audio"), 0);
//
//             assertThat(response.getTrackId()).isEqualTo(50);
//         }
//     }
//
// //     @Nested
// //     @DisplayName("removeTrack")
// //     class RemoveTrackTest {
//
// //         @Test
// //         @DisplayName("head 트랙 삭제 시 다음 트랙의 preTrackId가 null로 업데이트된다")
// //         void removeHeadTrack() throws JsonProcessingException {
// //             // A(1, head) → B(2)
// //             store.put("1", trackJson(1, null, 2));
// //             store.put("2", trackJson(2, 1, null));
//
// //             when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);
//
// //             TrackRemoveResponse response = trackService.removeTrack(removeRequest(1), 0);
//
// //             assertThat(response.getTrackId()).isEqualTo(1);
// //             assertThat(response.getPreTrackId()).isNull();
// //             assertThat(response.getPostTrackId()).isEqualTo(2);
//
// //             assertThat(fromStore(2).getPreTrackId()).isNull();
// //             verify(trackEqService).deleteByTrackIdIfExists(1);
// //         }
//
// //         @Test
// //         @DisplayName("tail 트랙 삭제 시 이전 트랙의 postTrackId가 null로 업데이트된다")
// //         void removeTailTrack() throws JsonProcessingException {
// //             // A(1) → B(2, tail)
// //             store.put("1", trackJson(1, null, 2));
// //             store.put("2", trackJson(2, 1, null));
//
// //             when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);
//
// //             TrackRemoveResponse response = trackService.removeTrack(removeRequest(2), 0);
//
// //             assertThat(response.getTrackId()).isEqualTo(2);
// //             assertThat(response.getPreTrackId()).isEqualTo(1);
// //             assertThat(response.getPostTrackId()).isNull();
//
// //             assertThat(fromStore(1).getPostTrackId()).isNull();
// //         }
//
// //         @Test
// //         @DisplayName("중간 트랙 삭제 시 앞뒤 트랙이 서로 연결된다")
// //         void removeMiddleTrack() throws JsonProcessingException {
// //             // A(1) → B(2) → C(3)
// //             store.put("1", trackJson(1, null, 2));
// //             store.put("2", trackJson(2, 1, 3));
// //             store.put("3", trackJson(3, 2, null));
//
// //             when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);
//
// //             TrackRemoveResponse response = trackService.removeTrack(removeRequest(2), 0);
//
// //             assertThat(response.getTrackId()).isEqualTo(2);
// //             assertThat(response.getPreTrackId()).isEqualTo(1);
// //             assertThat(response.getPostTrackId()).isEqualTo(3);
//
// //             assertThat(fromStore(1).getPostTrackId()).isEqualTo(3);
// //             assertThat(fromStore(3).getPreTrackId()).isEqualTo(1);
// //         }
// //     }
//
// //     @Nested
// //     @DisplayName("reorderTrack")
// //     class ReorderTrackTest {
//
// //         @Test
// //         @DisplayName("tail 트랙을 head로 이동 시 링크드 리스트가 올바르게 재구성된다")
// //         void reorderToHead() throws JsonProcessingException {
// //             // A(1) → B(2) → C(3), C를 head로 이동
// //             store.put("1", trackJson(1, null, 2));
// //             store.put("2", trackJson(2, 1, 3));
// //             store.put("3", trackJson(3, 2, null));
//
// //             when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);
//
// //             TrackReorderResponse response = trackService.reorderTrack(reorderRequest(3, null, 1), 0);
//
// //             assertThat(response.getTrackId()).isEqualTo(3);
// //             assertThat(response.getPreTrackId()).isNull();
// //             assertThat(response.getPostTrackId()).isEqualTo(1);
//
// //             // 최종 순서: C(3) → A(1) → B(2)
// //             assertThat(fromStore(3).getPreTrackId()).isNull();
// //             assertThat(fromStore(3).getPostTrackId()).isEqualTo(1);
// //             assertThat(fromStore(1).getPreTrackId()).isEqualTo(3);
// //             assertThat(fromStore(2).getPostTrackId()).isNull();
// //         }
//
// //         @Test
// //         @DisplayName("head 트랙을 tail로 이동 시 링크드 리스트가 올바르게 재구성된다")
// //         void reorderToTail() throws JsonProcessingException {
// //             // A(1) → B(2) → C(3), A를 tail로 이동
// //             store.put("1", trackJson(1, null, 2));
// //             store.put("2", trackJson(2, 1, 3));
// //             store.put("3", trackJson(3, 2, null));
//
// //             when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);
//
// //             TrackReorderResponse response = trackService.reorderTrack(reorderRequest(1, 3, null), 0);
//
// //             assertThat(response.getTrackId()).isEqualTo(1);
// //             assertThat(response.getPreTrackId()).isEqualTo(3);
// //             assertThat(response.getPostTrackId()).isNull();
//
// //             // 최종 순서: B(2) → C(3) → A(1)
// //             assertThat(fromStore(2).getPreTrackId()).isNull();
// //             assertThat(fromStore(3).getPostTrackId()).isEqualTo(1);
// //             assertThat(fromStore(1).getPreTrackId()).isEqualTo(3);
// //             assertThat(fromStore(1).getPostTrackId()).isNull();
// //         }
//
// //         @Test
// //         @DisplayName("트랙을 중간 위치로 이동 시 링크드 리스트가 올바르게 재구성된다")
// //         void reorderToMiddle() throws JsonProcessingException {
// //             // A(1) → B(2) → C(3) → D(4), D를 B와 C 사이로 이동
// //             store.put("1", trackJson(1, null, 2));
// //             store.put("2", trackJson(2, 1, 3));
// //             store.put("3", trackJson(3, 2, 4));
// //             store.put("4", trackJson(4, 3, null));
//
// //             when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);
//
// //             TrackReorderResponse response = trackService.reorderTrack(reorderRequest(4, 2, 3), 0);
//
// //             assertThat(response.getTrackId()).isEqualTo(4);
// //             assertThat(response.getPreTrackId()).isEqualTo(2);
// //             assertThat(response.getPostTrackId()).isEqualTo(3);
//
// //             // 최종 순서: A(1) → B(2) → D(4) → C(3)
// //             assertThat(fromStore(2).getPostTrackId()).isEqualTo(4);
// //             assertThat(fromStore(4).getPreTrackId()).isEqualTo(2);
// //             assertThat(fromStore(4).getPostTrackId()).isEqualTo(3);
// //             assertThat(fromStore(3).getPreTrackId()).isEqualTo(4);
// //             assertThat(fromStore(3).getPostTrackId()).isNull();
// //         }
// //     }
//
// //     @Nested
// //     @DisplayName("renameTrack")
// //     class RenameTrackTest {
//
// //         @Test
// //         @DisplayName("트랙명이 요청한 이름으로 변경된다")
// //         void renameTrack() throws JsonProcessingException {
// //             store.put("1", trackJson(1, null, null));
//
// //             when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);
//
// //             TrackRenameResponse response = trackService.renameTrack(renameRequest(1, "피아노 메인"), 0);
//
// //             assertThat(response.getTrackId()).isEqualTo(1);
// //             assertThat(response.getName()).isEqualTo("피아노 메인");
//
// //             assertThat(fromStore(1).getName()).isEqualTo("피아노 메인");
// //         }
//
// //         @Test
// //         @DisplayName("이름 변경 시 preTrackId, postTrackId 등 다른 필드는 변경되지 않는다")
// //         void renameDoesNotAffectOtherFields() throws JsonProcessingException {
// //             // A(1) → B(2) → C(3), 중간 트랙 B의 이름 변경
// //             store.put("1", trackJson(1, null, 2));
// //             store.put("2", trackJson(2, 1, 3));
// //             store.put("3", trackJson(3, 2, null));
//
// //             when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);
//
// //             trackService.renameTrack(renameRequest(2, "드럼"), 0);
//
// //             TrackState renamed = fromStore(2);
// //             assertThat(renamed.getName()).isEqualTo("드럼");
// //             assertThat(renamed.getPreTrackId()).isEqualTo(1);
// //             assertThat(renamed.getPostTrackId()).isEqualTo(3);
// //             assertThat(renamed.getType()).isEqualTo("audio");
// //             assertThat(renamed.getIsMuted()).isFalse();
// //             assertThat(renamed.getIsSoloed()).isFalse();
// //         }
//
// //         @Test
// //         @DisplayName("존재하지 않는 트랙 이름 변경 시 TRACK_NOT_FOUND 예외가 발생한다")
// //         void renameNotFoundTrack() {
// //             org.junit.jupiter.api.Assertions.assertThrows(BusinessException.class, () ->
// //                     trackService.renameTrack(renameRequest(99, "없는트랙"), 0)
// //             );
// //         }
// //     }
//
// //     @Nested
// //     @DisplayName("soloTrack")
// //     class SoloTrackTest {
//
// //         @Test
// //         @DisplayName("isSoloed를 true로 변경하면 Redis 상태에 반영된다")
// //         void soloTrackOn() throws JsonProcessingException {
// //             store.put("1", trackJson(1, null, null));
//
// //             TrackSoloResponse response = trackService.soloTrack(soloRequest(1, true));
//
// //             assertThat(response.getTrackId()).isEqualTo(1);
// //             assertThat(response.getIsSoloed()).isTrue();
// //             assertThat(fromStore(1).getIsSoloed()).isTrue();
// //         }
//
// //         @Test
// //         @DisplayName("isSoloed를 false로 변경하면 Redis 상태에 반영된다")
// //         void soloTrackOff() throws JsonProcessingException {
// //             store.put("1", objectMapper.writeValueAsString(TrackState.builder()
// //                     .trackId(1).name("track1").type("audio")
// //                     .preTrackId(null).postTrackId(null)
// //                     .isMuted(false).isSoloed(true).volume(0.0).pan(0)
// //                     .build()));
//
// //             TrackSoloResponse response = trackService.soloTrack(soloRequest(1, false));
//
// //             assertThat(response.getIsSoloed()).isFalse();
// //             assertThat(fromStore(1).getIsSoloed()).isFalse();
// //         }
//
// //         @Test
// //         @DisplayName("솔로 변경 시 다른 필드는 변경되지 않는다")
// //         void soloDoesNotAffectOtherFields() throws JsonProcessingException {
// //             store.put("2", trackJson(2, 1, 3));
//
// //             trackService.soloTrack(soloRequest(2, true));
//
// //             TrackState result = fromStore(2);
// //             assertThat(result.getIsSoloed()).isTrue();
// //             assertThat(result.getPreTrackId()).isEqualTo(1);
// //             assertThat(result.getPostTrackId()).isEqualTo(3);
// //             assertThat(result.getName()).isEqualTo("track2");
// //             assertThat(result.getIsMuted()).isFalse();
// //         }
//
// //         @Test
// //         @DisplayName("존재하지 않는 트랙 솔로 변경 시 TRACK_NOT_FOUND 예외가 발생한다")
// //         void soloNotFoundTrack() {
// //             org.junit.jupiter.api.Assertions.assertThrows(BusinessException.class, () ->
// //                     trackService.soloTrack(soloRequest(99, true))
// //             );
// //         }
// //     }
//
// //     @Nested
// //     @DisplayName("muteTrack")
// //     class MuteTrackTest {
//
// //         @Test
// //         @DisplayName("isMuted를 true로 변경하면 Redis 상태에 반영된다")
// //         void muteTrackOn() throws JsonProcessingException {
// //             store.put("1", trackJson(1, null, null));
//
// //             TrackMuteResponse response = trackService.muteTrack(muteRequest(1, true));
//
// //             assertThat(response.getTrackId()).isEqualTo(1);
// //             assertThat(response.getIsMuted()).isTrue();
// //             assertThat(fromStore(1).getIsMuted()).isTrue();
// //         }
//
// //         @Test
// //         @DisplayName("isMuted를 false로 변경하면 Redis 상태에 반영된다")
// //         void muteTrackOff() throws JsonProcessingException {
// //             store.put("1", objectMapper.writeValueAsString(TrackState.builder()
// //                     .trackId(1).name("track1").type("audio")
// //                     .preTrackId(null).postTrackId(null)
// //                     .isMuted(true).isSoloed(false).volume(0.0).pan(0)
// //                     .build()));
//
// //             TrackMuteResponse response = trackService.muteTrack(muteRequest(1, false));
//
// //             assertThat(response.getIsMuted()).isFalse();
// //             assertThat(fromStore(1).getIsMuted()).isFalse();
// //         }
//
// //         @Test
// //         @DisplayName("뮤트 변경 시 다른 필드는 변경되지 않는다")
// //         void muteDoesNotAffectOtherFields() throws JsonProcessingException {
// //             store.put("2", trackJson(2, 1, 3));
//
// //             trackService.muteTrack(muteRequest(2, true));
//
// //             TrackState result = fromStore(2);
// //             assertThat(result.getIsMuted()).isTrue();
// //             assertThat(result.getPreTrackId()).isEqualTo(1);
// //             assertThat(result.getPostTrackId()).isEqualTo(3);
// //             assertThat(result.getName()).isEqualTo("track2");
// //             assertThat(result.getIsSoloed()).isFalse();
// //         }
//
// //         @Test
// //         @DisplayName("존재하지 않는 트랙 뮤트 변경 시 TRACK_NOT_FOUND 예외가 발생한다")
// //         void muteNotFoundTrack() {
// //             org.junit.jupiter.api.Assertions.assertThrows(BusinessException.class, () ->
// //                     trackService.muteTrack(muteRequest(99, true))
// //             );
// //         }
// //     }
//
// //     @Nested
// //     @DisplayName("changeVolume")
// //     class ChangeVolumeTest {
//
// //         @Test
// //         @DisplayName("볼륨이 요청한 값으로 변경된다")
// //         void changeVolume() throws JsonProcessingException {
// //             store.put("1", trackJson(1, null, null));
//
// //             TrackVolumeResponse response = trackService.changeVolume(volumeRequest(1, 80.0));
//
// //             assertThat(response.getTrackId()).isEqualTo(1);
// //             assertThat(response.getVolume()).isEqualTo(80.0);
// //             assertThat(fromStore(1).getVolume()).isEqualTo(80.0);
// //         }
//
// //         @Test
// //         @DisplayName("볼륨 변경 시 다른 필드는 변경되지 않는다")
// //         void changeVolumeDoesNotAffectOtherFields() throws JsonProcessingException {
// //             store.put("2", trackJson(2, 1, 3));
//
// //             trackService.changeVolume(volumeRequest(2, 50.0));
//
// //             TrackState result = fromStore(2);
// //             assertThat(result.getVolume()).isEqualTo(50.0);
// //             assertThat(result.getPreTrackId()).isEqualTo(1);
// //             assertThat(result.getPostTrackId()).isEqualTo(3);
// //             assertThat(result.getName()).isEqualTo("track2");
// //             assertThat(result.getIsMuted()).isFalse();
// //             assertThat(result.getIsSoloed()).isFalse();
// //         }
//
// //         @Test
// //         @DisplayName("존재하지 않는 트랙 볼륨 변경 시 TRACK_NOT_FOUND 예외가 발생한다")
// //         void changeVolumeNotFoundTrack() {
// //             org.junit.jupiter.api.Assertions.assertThrows(BusinessException.class, () ->
// //                     trackService.changeVolume(volumeRequest(99, 80.0))
// //             );
// //         }
// //     }
//
// //     @Nested
// //     @DisplayName("changePan")
// //     class ChangePanTest {
//
// //         @Test
// //         @DisplayName("패닝이 요청한 값으로 변경된다")
// //         void changePan() throws JsonProcessingException {
// //             store.put("1", trackJson(1, null, null));
//
// //             TrackPanResponse response = trackService.changePan(panRequest(1, 50));
//
// //             assertThat(response.getTrackId()).isEqualTo(1);
// //             assertThat(response.getPan()).isEqualTo(50);
// //             assertThat(fromStore(1).getPan()).isEqualTo(50);
// //         }
//
// //         @Test
// //         @DisplayName("패닝 변경 시 다른 필드는 변경되지 않는다")
// //         void changePanDoesNotAffectOtherFields() throws JsonProcessingException {
// //             store.put("2", trackJson(2, 1, 3));
//
// //             trackService.changePan(panRequest(2, -30));
//
// //             TrackState result = fromStore(2);
// //             assertThat(result.getPan()).isEqualTo(-30);
// //             assertThat(result.getPreTrackId()).isEqualTo(1);
// //             assertThat(result.getPostTrackId()).isEqualTo(3);
// //             assertThat(result.getName()).isEqualTo("track2");
// //             assertThat(result.getIsMuted()).isFalse();
// //             assertThat(result.getIsSoloed()).isFalse();
// //             assertThat(result.getVolume()).isEqualTo(0.0);
// //         }
//
// //         @Test
// //         @DisplayName("존재하지 않는 트랙 패닝 변경 시 TRACK_NOT_FOUND 예외가 발생한다")
// //         void changePanNotFoundTrack() {
// //             org.junit.jupiter.api.Assertions.assertThrows(BusinessException.class, () ->
// //                     trackService.changePan(panRequest(99, 50))
// //             );
// //         }
// //     }
// // }
