package com.salmon.studion.domain.eq.service;

import com.salmon.studion.domain.eq.dto.request.BandRequest;
import com.salmon.studion.domain.eq.dto.response.TrackEqBandListResponse;
import com.salmon.studion.domain.eq.entity.TrackEq;
import com.salmon.studion.domain.eq.entity.TrackEqBand;
import com.salmon.studion.domain.eq.repository.TrackEqBandRepository;
import com.salmon.studion.domain.eq.repository.TrackEqRepository;
import com.salmon.studion.global.exception.BusinessException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.SetOperations;
import org.springframework.test.util.ReflectionTestUtils;

import java.lang.reflect.Constructor;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TrackEqBandServiceTest {

    @Mock
    private TrackEqBandRepository trackEqBandRepository;

    @Mock
    private TrackEqRepository trackEqRepository;

    @Mock
    private com.salmon.studion.domain.project.service.ProjectMemberService projectMemberService;

    @Mock
    private RedisTemplate<String, String> redisTemplate;

    @Mock
    private SetOperations<String, String> setOperations;

    @InjectMocks
    private TrackEqBandService trackEqBandService;

    @Test
    @DisplayName("replaceTrackEqBands는 삭제 예약되지 않은 EQ만 교체 저장한다")
    void replaceTrackEqBandsReplacesBands() {
        TrackEq trackEq = TrackEq.create(5, 1);
        ReflectionTestUtils.setField(trackEq, "id", 7);
        when(trackEqRepository.findById(7)).thenReturn(Optional.of(trackEq));
        when(redisTemplate.opsForSet()).thenReturn(setOperations);
        when(setOperations.isMember("project:1:deleted_track_eq_tracks", "5")).thenReturn(false);

        List<BandRequest> requests = List.of(
                bandRequest(1, "BELL", 250, 1.2, -3.0, "USER_MANUAL"),
                bandRequest(2, "HIGH_SHELF", 4000, 0.7, 1.5, "SYSTEM")
        );

        trackEqBandService.replaceTrackEqBands(7, 99, requests);

        verify(projectMemberService).validateProjectMember(1, 99);
        verify(trackEqBandRepository).deleteAllByTrackEq_Id(7);

        ArgumentCaptor<List<TrackEqBand>> captor = ArgumentCaptor.forClass(List.class);
        verify(trackEqBandRepository).saveAll(captor.capture());

        List<TrackEqBand> saved = captor.getValue();
        assertThat(saved).hasSize(2);
        assertThat(saved.get(0).getTrackEq()).isSameAs(trackEq);
        assertThat(saved.get(0).getBandOrder()).isEqualTo(1);
        assertThat(saved.get(0).getEqTypeCode()).isEqualTo(1);
        assertThat(saved.get(0).getSourceTypeCode()).isEqualTo(2);
        assertThat(saved.get(1).getEqTypeCode()).isEqualTo(3);
        assertThat(saved.get(1).getSourceTypeCode()).isEqualTo(3);
    }

    @Test
    @DisplayName("replaceTrackEqBands는 삭제 예약된 EQ를 다시 저장하지 않는다")
    void replaceTrackEqBandsRejectsDeletedTrackEq() {
        TrackEq trackEq = TrackEq.create(5, 1);
        ReflectionTestUtils.setField(trackEq, "id", 7);
        when(trackEqRepository.findById(7)).thenReturn(Optional.of(trackEq));
        when(redisTemplate.opsForSet()).thenReturn(setOperations);
        when(setOperations.isMember("project:1:deleted_track_eq_tracks", "5")).thenReturn(true);

        assertThatThrownBy(() -> trackEqBandService.replaceTrackEqBands(
                7,
                99,
                List.of(bandRequest(1, "BELL", 250, 1.2, -3.0, "USER_MANUAL"))
        )).isInstanceOf(BusinessException.class);

        verify(trackEqBandRepository, never()).deleteAllByTrackEq_Id(7);
        verify(trackEqBandRepository, never()).saveAll(any());
    }

    @Test
    @DisplayName("getTrackEqBandList는 entity를 응답 DTO로 변환한다")
    void getTrackEqBandListMapsResponse() {
        TrackEq trackEq = TrackEq.create(5, 1);
        ReflectionTestUtils.setField(trackEq, "id", 7);

        TrackEqBand first = TrackEqBand.create(trackEq, 1, 1, 250, 1.2, -3.0, null, null, null, 2);
        TrackEqBand second = TrackEqBand.create(trackEq, 2, 3, 4000, 0.7, 1.5, null, null, null, 3);
        ReflectionTestUtils.setField(first, "id", 101);
        ReflectionTestUtils.setField(second, "id", 102);

        when(trackEqRepository.findById(7)).thenReturn(Optional.of(trackEq));
        when(trackEqBandRepository.findByTrackEq_IdOrderByBandOrderAsc(7)).thenReturn(List.of(first, second));
        when(redisTemplate.opsForSet()).thenReturn(setOperations);
        when(setOperations.isMember("project:1:deleted_track_eq_tracks", "5")).thenReturn(false);

        TrackEqBandListResponse response = trackEqBandService.getTrackEqBandList(7, 99);

        verify(projectMemberService).validateProjectMember(1, 99);
        assertThat(response.getTrackEqBandSummaries()).hasSize(2);
        assertThat(response.getTrackEqBandSummaries().get(0).trackEqBandId()).isEqualTo(101);
        assertThat(response.getTrackEqBandSummaries().get(0).eqType()).isEqualTo("BELL");
        assertThat(response.getTrackEqBandSummaries().get(0).sourceType()).isEqualTo("USER_MANUAL");
        assertThat(response.getTrackEqBandSummaries().get(1).eqType()).isEqualTo("HIGH_SHELF");
        assertThat(response.getTrackEqBandSummaries().get(1).sourceType()).isEqualTo("SYSTEM");
    }

    private BandRequest bandRequest(
            Integer bandOrder,
            String eqType,
            Integer frequencyHz,
            Double q,
            Double gainDeltaDb,
            String sourceType
    ) {
        try {
            Constructor<BandRequest> constructor = BandRequest.class.getDeclaredConstructor();
            constructor.setAccessible(true);
            BandRequest request = constructor.newInstance();
            ReflectionTestUtils.setField(request, "bandOrder", bandOrder);
            ReflectionTestUtils.setField(request, "eqType", eqType);
            ReflectionTestUtils.setField(request, "frequencyHz", frequencyHz);
            ReflectionTestUtils.setField(request, "q", q);
            ReflectionTestUtils.setField(request, "gainDeltaDb", gainDeltaDb);
            ReflectionTestUtils.setField(request, "sourceType", sourceType);
            return request;
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }
}
