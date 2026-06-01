package com.salmon.studion.domain.eq.controller;

import com.salmon.studion.domain.eq.dto.request.TrackEqBandSaveRequest;
import com.salmon.studion.domain.eq.dto.response.TrackEqBandListResponse;
import com.salmon.studion.domain.eq.dto.response.TrackEqListResponse;
import com.salmon.studion.domain.eq.service.TrackEqBandService;
import com.salmon.studion.domain.eq.service.TrackEqService;
import com.salmon.studion.global.auth.CustomOAuth2User;
import com.salmon.studion.global.common.response.ApiResponse;
import com.salmon.studion.global.common.response.SuccessCode;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/eq")
@RequiredArgsConstructor
public class TrackEqController {

    private final TrackEqService trackEqService;
    private final TrackEqBandService trackEqBandService;

    /**
     * project에 있는 track eq 리스트 조회 API
     * 프로젝트 진입 시 호출하는 API
     *
     * @param projectId
     * @param user
     * @return
     */
    @GetMapping("/projects/{projectId}/track-eqs")
    public ResponseEntity<ApiResponse<TrackEqListResponse>> getProjectTrackEqs(
            @PathVariable Integer projectId,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(
                trackEqService.getProjectTrackEqList(projectId, user.getUserId())
        ));
    }

    /**
     * track eq를 이용한 track eq band 조회 API
     * 프로젝트 진입 시 호출 x -> 트랙을 클릭했을 때 호출하는 API
     *
     * @param trackEqId
     * @param user
     * @return
     */
    @GetMapping("/track-eqs/{trackEqId}/bands")
    public ResponseEntity<ApiResponse<TrackEqBandListResponse>> getProjectTrackEqBands(
            @PathVariable Integer trackEqId,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(
                trackEqBandService.getTrackEqBandList(trackEqId, user.getUserId())
        ));
    }

    /**
     * 프로젝트를 저장할 때 track eq band를 저장하는 API
     *
     * @param trackEqId
     * @param user
     * @param request
     * @return
     */
    @PostMapping("/track-eqs/{trackEqId}/bands")
    public ResponseEntity<ApiResponse<Void>> saveTrackEqBands(
            @PathVariable Integer trackEqId,
            @AuthenticationPrincipal CustomOAuth2User user,
            @Valid @RequestBody TrackEqBandSaveRequest request
    ) {
        trackEqBandService.replaceTrackEqBands(trackEqId, user.getUserId(), request.getBands());
        return ResponseEntity.ok(ApiResponse.success(SuccessCode.EQ_UPDATED));
    }

    @DeleteMapping("/track-eqs/{trackEqId}/bands")
    public ResponseEntity<ApiResponse<Void>> clearTrackEqBands(
            @PathVariable Integer trackEqId,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        trackEqBandService.deleteTrackEqBands(trackEqId, user.getUserId());
        return ResponseEntity.ok(ApiResponse.success(SuccessCode.EQ_UPDATED));
    }
}
