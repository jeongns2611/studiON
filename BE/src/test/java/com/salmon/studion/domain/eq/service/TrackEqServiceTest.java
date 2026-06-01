package com.salmon.studion.domain.eq.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.eq.entity.TrackEq;
import com.salmon.studion.domain.eq.repository.TrackEqBandRepository;
import com.salmon.studion.domain.eq.repository.TrackEqRepository;
import com.salmon.studion.domain.project.service.ProjectMemberService;
import com.salmon.studion.domain.project.service.ProjectService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.SetOperations;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TrackEqServiceTest {

    @Mock
    private TrackEqRepository trackEqRepository;

    @Mock
    private TrackEqBandRepository trackEqBandRepository;

    @Mock
    private ProjectService projectService;

    @Mock
    private ProjectMemberService projectMemberService;

    @Mock
    private RedisTemplate<String, String> redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOperations;

    @Mock
    private SetOperations<String, String> setOperations;

    @Mock
    private TrackEqBandService trackEqBandService;

    @Spy
    private ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();

    @InjectMocks
    private TrackEqService trackEqService;

    @Test
    @DisplayName("트랙 삭제 시 EQ는 즉시 DB 삭제하지 않고 deleted-set에만 적재한다")
    void deleteByTrackIdIfExistsMarksDeletedOnly() {
        TrackEq trackEq = trackEq(7, 11, 22);
        when(trackEqRepository.findByTrackId(11)).thenReturn(Optional.of(trackEq));
        when(redisTemplate.opsForSet()).thenReturn(setOperations);

        trackEqService.deleteByTrackIdIfExists(11);

        verify(redisTemplate).delete("project:22:track-eq:7:lock");
        verify(redisTemplate).delete("project:22:track-eq:7:draft");
        verify(redisTemplate).delete("project:22:track:11:eq:current");
        verify(setOperations).add("project:22:deleted_track_eq_tracks", "11");
        verify(trackEqBandRepository, never()).deleteAllByTrackEq_Id(any());
        verify(trackEqRepository, never()).delete(any());
    }

    @Test
    @DisplayName("삭제 예약된 트랙 EQ는 목록 응답에서 제외한다")
    void getProjectTrackEqListFiltersDeletedTracks() {
        when(redisTemplate.opsForSet()).thenReturn(setOperations);
        when(setOperations.members("project:22:deleted_track_eq_tracks")).thenReturn(Set.of("11"));
        when(trackEqRepository.findByProjectId(22)).thenReturn(List.of(
                trackEq(7, 11, 22),
                trackEq(8, 12, 22)
        ));

        var response = trackEqService.getProjectTrackEqList(22, 99);

        verify(projectService).getProjectOrThrow(22);
        verify(projectMemberService).validateProjectMember(22, 99);
        assertThat(response.getTrackEqs()).hasSize(1);
        assertThat(response.getTrackEqs().get(0).trackId()).isEqualTo(12);
    }

    @Test
    @DisplayName("삭제 예약된 트랙 EQ는 현재 payload 생성에서 제외한다")
    void getCurrentTrackEqPayloadsSkipsDeletedTracks() {
        when(redisTemplate.opsForSet()).thenReturn(setOperations);
        when(setOperations.isMember("project:1:deleted_track_eq_tracks", "30")).thenReturn(true);

        var payloads = trackEqService.getCurrentTrackEqPayloads(1, List.of(30));

        assertThat(payloads).isEmpty();
        verifyNoInteractions(trackEqRepository, trackEqBandRepository);
    }

    @Test
    @DisplayName("createIfAbsent는 삭제 예약된 트랙에 새 EQ를 만들지 않는다")
    void createIfAbsentSkipsDeletedTrack() {
        when(redisTemplate.opsForSet()).thenReturn(setOperations);
        when(setOperations.isMember("project:22:deleted_track_eq_tracks", "11")).thenReturn(true);

        trackEqService.createIfAbsent(11, 22);

        verify(trackEqRepository, never()).existsByTrackId(11);
        verify(trackEqRepository, never()).save(any());
    }

    @Test
    @DisplayName("snapshot save 시 deleted-set과 orphan 기준으로 EQ를 정리하고 필요한 EQ만 생성한다")
    void synchronizeWithTrackIdsDeletesMarkedAndOrphansThenCreatesMissing() {
        TrackEq deletedEq = trackEq(7, 11, 22);
        TrackEq orphanEq = trackEq(8, 12, 22);
        TrackEq persistedEq = trackEq(9, 13, 22);
        TrackEq createdEq = trackEq(10, 14, 22);

        when(redisTemplate.opsForSet()).thenReturn(setOperations);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(setOperations.members("project:22:deleted_track_eq_tracks")).thenReturn(Set.of("11"));
        when(trackEqRepository.findByProjectId(22)).thenReturn(List.of(deletedEq, orphanEq, persistedEq));
        when(trackEqRepository.saveAll(any())).thenReturn(List.of(createdEq));

        trackEqService.synchronizeWithTrackIds(22, List.of(13, 14));

        verify(trackEqBandRepository).deleteAllByTrackEq_IdIn(List.of(7, 8));
        verify(redisTemplate).delete("project:22:track-eq:7:lock");
        verify(redisTemplate).delete("project:22:track-eq:7:draft");
        verify(redisTemplate).delete("project:22:track:11:eq:current");
        verify(redisTemplate).delete("project:22:track-eq:8:lock");
        verify(redisTemplate).delete("project:22:track-eq:8:draft");
        verify(redisTemplate).delete("project:22:track:12:eq:current");
        verify(trackEqRepository).deleteAllByIdInBatch(List.of(7, 8));
        verify(valueOperations).set(eq("project:22:track:14:eq:current"), any(String.class));
        verify(redisTemplate).delete("project:22:deleted_track_eq_tracks");
    }

    private TrackEq trackEq(Integer id, Integer trackId, Integer projectId) {
        TrackEq trackEq = TrackEq.create(trackId, projectId);
        ReflectionTestUtils.setField(trackEq, "id", id);
        return trackEq;
    }
}
