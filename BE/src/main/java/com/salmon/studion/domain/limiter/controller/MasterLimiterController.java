package com.salmon.studion.domain.limiter.controller;

import com.salmon.studion.domain.limiter.dto.MasterLimiterCurrentState;
import com.salmon.studion.domain.limiter.dto.MasterLimiterDraftState;
import com.salmon.studion.domain.limiter.dto.request.MasterLimiterCommitRequest;
import com.salmon.studion.domain.limiter.dto.request.MasterLimiterDraftSaveRequest;
import com.salmon.studion.domain.limiter.dto.request.MasterLimiterLockRequest;
import com.salmon.studion.domain.limiter.dto.request.MasterLimiterResetRequest;
import com.salmon.studion.domain.limiter.dto.response.MasterLimiterLockResponse;
import com.salmon.studion.domain.limiter.service.MasterLimiterService;
import com.salmon.studion.global.auth.CustomOAuth2User;
import com.salmon.studion.global.common.response.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/limiter")
@RequiredArgsConstructor
public class MasterLimiterController {

    private final MasterLimiterService masterLimiterService;

    @GetMapping("/projects/{projectId}")
    public ResponseEntity<ApiResponse<MasterLimiterCurrentState>> getProjectMasterLimiter(
            @PathVariable Integer projectId,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(
                masterLimiterService.getProjectMasterLimiter(projectId, user.getUserId())
        ));
    }

    @PostMapping("/projects/{projectId}/lock")
    public ResponseEntity<ApiResponse<MasterLimiterLockResponse>> lockProjectMasterLimiter(
            @PathVariable Integer projectId,
            @RequestBody MasterLimiterLockRequest request,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        request.setProjectId(projectId);
        return ResponseEntity.ok(ApiResponse.success(
                masterLimiterService.lockMasterLimiter(request, user.getUserId())
        ));
    }

    @PostMapping("/projects/{projectId}/draft")
    public ResponseEntity<ApiResponse<MasterLimiterDraftState>> saveProjectMasterLimiterDraft(
            @PathVariable Integer projectId,
            @RequestBody MasterLimiterDraftSaveRequest request,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        request.setProjectId(projectId);
        return ResponseEntity.ok(ApiResponse.success(
                masterLimiterService.saveDraft(request, user.getUserId())
        ));
    }

    @PostMapping("/projects/{projectId}/reset")
    public ResponseEntity<ApiResponse<MasterLimiterCurrentState>> resetProjectMasterLimiterDraft(
            @PathVariable Integer projectId,
            @RequestBody MasterLimiterResetRequest request,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        request.setProjectId(projectId);
        return ResponseEntity.ok(ApiResponse.success(
                masterLimiterService.resetDraft(request, user.getUserId())
        ));
    }

    @PostMapping("/projects/{projectId}/commit")
    public ResponseEntity<ApiResponse<MasterLimiterCurrentState>> commitProjectMasterLimiterDraft(
            @PathVariable Integer projectId,
            @RequestBody MasterLimiterCommitRequest request,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        request.setProjectId(projectId);
        return ResponseEntity.ok(ApiResponse.success(
                masterLimiterService.commitDraft(request, user.getUserId())
        ));
    }
}
