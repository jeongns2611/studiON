package com.salmon.studion.domain.ai.controller;

import com.salmon.studion.domain.ai.dto.request.AiJobStartApiRequest;
import com.salmon.studion.domain.ai.dto.request.AiUserFeedbackApiRequest;
import com.salmon.studion.domain.ai.dto.response.AiJobStartResponse;
import com.salmon.studion.domain.ai.dto.response.AiWorkflowJobResponse;
import com.salmon.studion.domain.ai.dto.response.AiWorkflowStatusResponse;
import com.salmon.studion.domain.ai.service.AiService;
import com.salmon.studion.global.auth.CustomOAuth2User;
import com.salmon.studion.global.common.response.ApiResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Slf4j
@RequiredArgsConstructor
@RequestMapping("/api/v1/ai")
public class AiController {

    private final AiService aiService;

    @PostMapping("/workflow/jobs/start")
    public ResponseEntity<ApiResponse<AiJobStartResponse>> startWorkflow(
            @Valid @RequestBody AiJobStartApiRequest request,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        Integer requestedBy = user != null ? user.getUserId() : null;
        log.info("AiController startWorkflow 호출 | projectId={} requestedBy={}",
                request.getProjectId(), requestedBy);
        return ResponseEntity.ok(ApiResponse.success(aiService.startWorkflow(request, requestedBy)));
    }

    @GetMapping("/workflow/jobs/{jobId}")
    public ResponseEntity<ApiResponse<AiWorkflowStatusResponse>> getWorkflowStatus(
            @PathVariable Integer jobId,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        Integer requestedBy = user != null ? user.getUserId() : null;
        log.info("AiController getWorkflowStatus 호출 | jobId={} requestedBy={}", jobId, requestedBy);
        return ResponseEntity.ok(ApiResponse.success(aiService.getWorkflowStatus(jobId, requestedBy)));
    }

    @PostMapping("/workflow/jobs/{jobId}/feedback")
    public ResponseEntity<ApiResponse<AiWorkflowJobResponse>> resumeWorkflowJob(
            @PathVariable Integer jobId,
            @Valid @RequestBody AiUserFeedbackApiRequest request,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        Integer requestedBy = user != null ? user.getUserId() : null;
        log.info("AiController resumeWorkflowJob 호출 | jobId={} projectId={} requestedBy={}",
                jobId, request.getProjectId(), requestedBy);
        return ResponseEntity.ok(ApiResponse.success(
                aiService.dispatchUserFeedback(jobId, request, requestedBy)
        ));
    }
}
