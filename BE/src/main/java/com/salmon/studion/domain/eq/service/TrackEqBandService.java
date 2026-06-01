package com.salmon.studion.domain.eq.service;

import com.salmon.studion.domain.eq.dto.TrackEqDraftState;
import com.salmon.studion.domain.eq.dto.request.BandRequest;
import com.salmon.studion.domain.eq.dto.response.TrackEqBandListResponse;
import com.salmon.studion.domain.eq.entity.TrackEq;
import com.salmon.studion.domain.eq.entity.TrackEqBand;
import com.salmon.studion.domain.eq.repository.TrackEqBandRepository;
import com.salmon.studion.domain.eq.repository.TrackEqRepository;
import com.salmon.studion.domain.eq.support.TrackEqRedisKeys;
import com.salmon.studion.domain.project.service.ProjectMemberService;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class TrackEqBandService {

    private final TrackEqBandRepository trackEqBandRepository;
    private final TrackEqRepository trackEqRepository;
    private final ProjectMemberService projectMemberService;
    private final RedisTemplate<String, String> redisTemplate;

    public TrackEqBandListResponse getTrackEqBandList(Integer trackEqId, Integer userId) {

        getAuthorizedTrackEq(trackEqId, userId);

        List<TrackEqBand> trackEqBands = trackEqBandRepository.findByTrackEq_IdOrderByBandOrderAsc(trackEqId);

        return TrackEqBandListResponse.builder()
                .trackEqBandSummaries(trackEqBands.stream()
                        .map(trackEqBand -> new TrackEqBandListResponse.TrackEqBandSummary(
                                trackEqBand.getId(),
                                trackEqBand.getTrackEq().getId(),
                                trackEqBand.getBandOrder(),
                                toEqType(trackEqBand.getEqTypeCode()),
                                trackEqBand.getFrequencyHz(),
                                trackEqBand.getQ(),
                                trackEqBand.getGainDeltaDb(),
                                trackEqBand.getJobId(),
                                trackEqBand.getSuggestionActionId(),
                                trackEqBand.getAppliedSuggestionId(),
                                toSourceTypeForProjection(trackEqBand.getSourceTypeCode())
                        ))
                        .toList())
                .build();
    }

    @Transactional
    public void replaceTrackEqBands(Integer trackEqId, Integer userId, List<BandRequest> bands) {

        TrackEq trackEq = getAuthorizedTrackEq(trackEqId, userId);

        trackEqBandRepository.deleteAllByTrackEq_Id(trackEqId);

        List<TrackEqBand> trackEqBands = bands.stream()
                .map(bandRequest -> toEntity(trackEq, bandRequest))
                .toList();

        trackEqBandRepository.saveAll(trackEqBands);
    }

    @Transactional
    public void replaceTrackEqBandsFromDraft(Integer trackEqId, Integer userId, List<TrackEqDraftState.DraftBand> bands) {

        TrackEq trackEq = getAuthorizedTrackEq(trackEqId, userId);

        trackEqBandRepository.deleteAllByTrackEq_Id(trackEqId);

        List<TrackEqBand> trackEqBands = bands.stream()
                .map(draftBand -> toEntity(trackEq, draftBand))
                .toList();

        trackEqBandRepository.saveAll(trackEqBands);
    }

    // 초기화 시 해당 trackEqId의 track eq bands 삭제
    @Transactional
    public void deleteTrackEqBands(Integer trackEqId, Integer userId) {

        getAuthorizedTrackEq(trackEqId, userId);

        trackEqBandRepository.deleteAllByTrackEq_Id(trackEqId);
    }

    private TrackEq getAuthorizedTrackEq(Integer trackEqId, Integer userId) {
        // 존재하지 않는 track eq면 예외 처리
        TrackEq trackEq = trackEqRepository.findById(trackEqId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TRACK_EQ_NOT_FOUND));

        projectMemberService.validateProjectMember(trackEq.getProjectId(), userId);
        if (Boolean.TRUE.equals(redisTemplate.opsForSet().isMember(
                TrackEqRedisKeys.deletedTrackEqsKey(trackEq.getProjectId()),
                String.valueOf(trackEq.getTrackId())
        ))) {
            throw new BusinessException(ErrorCode.TRACK_EQ_NOT_FOUND);
        }

        return trackEq;
    }

    private TrackEqBand toEntity(TrackEq trackEq, BandRequest request) {
        return TrackEqBand.create(
                trackEq,
                request.getBandOrder(),
                toEqTypeCode(request.getEqType()),
                request.getFrequencyHz(),
                request.getQ(),
                request.getGainDeltaDb(),
                request.getJobId(),
                request.getSuggestionActionId(),
                request.getAppliedSuggestionId(),
                toSourceTypeCode(request.getSourceType())
        );
    }

    private TrackEqBand toEntity(TrackEq trackEq, TrackEqDraftState.DraftBand request) {
        return TrackEqBand.create(
                trackEq,
                request.getBandOrder(),
                toEqTypeCode(request.getEqType()),
                request.getFrequencyHz(),
                request.getQ(),
                request.getGainDeltaDb(),
                request.getJobId(),
                request.getSuggestionActionId(),
                request.getAppliedSuggestionId(),
                toSourceTypeCode(request.getSourceType())
        );
    }

    private Integer toEqTypeCode(String eqType) {
        return switch (eqType) {
            case "BELL" -> 1;
            case "LOW_SHELF" -> 2;
            case "HIGH_SHELF" -> 3;
            default -> throw new BusinessException(ErrorCode.INVALID_INPUT_VALUE, "지원하지 않는 eqType입니다: " + eqType);
        };
    }

    private String toEqType(Integer eqTypeCode) {
        if (eqTypeCode == null) {
            return null;
        }

        return switch (eqTypeCode) {
            case 1 -> "BELL";
            case 2 -> "LOW_SHELF";
            case 3 -> "HIGH_SHELF";
            default -> "UNKNOWN";
        };
    }

    private Integer toSourceTypeCode(String sourceType) {
        return switch (sourceType) {
            case "AI_CONFIRM", "AI_APPLIED" -> 1;
            case "USER_MANUAL" -> 2;
            case "SYSTEM" -> 3;
            default -> throw new BusinessException(ErrorCode.INVALID_INPUT_VALUE, "지원하지 않는 sourceType입니다: " + sourceType);
        };
    }

    String toSourceTypeForProjection(Integer sourceTypeCode) {
        if (sourceTypeCode == null) {
            return null;
        }

        return switch (sourceTypeCode) {
            case 1 -> "AI_CONFIRM";
            case 2 -> "USER_MANUAL";
            case 3 -> "SYSTEM";
            default -> "UNKNOWN";
        };
    }
}
