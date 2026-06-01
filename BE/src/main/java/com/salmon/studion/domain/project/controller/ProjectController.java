package com.salmon.studion.domain.project.controller;

import com.salmon.studion.domain.project.dto.request.ProjectCreateRequest;
import com.salmon.studion.domain.project.dto.response.ProjectCreateResponse;
import com.salmon.studion.domain.project.dto.response.ProjectDetailResponse;
import com.salmon.studion.domain.project.dto.response.ProjectListResponse;
import com.salmon.studion.domain.project.dto.response.ProjectSnapshotSaveResponse;
import com.salmon.studion.domain.project.facade.ProjectFacade;
import com.salmon.studion.global.auth.CustomOAuth2User;
import com.salmon.studion.global.common.response.ApiResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/projects")
@RequiredArgsConstructor
public class ProjectController {

    private final ProjectFacade projectFacade;

    @GetMapping("/{projectId}")
    public ResponseEntity<ApiResponse<ProjectDetailResponse>> getProject(
            @PathVariable Integer projectId,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(projectFacade.getProjectDetail(projectId, user.getUserId())));
    }

    @GetMapping()
    public ResponseEntity<ApiResponse<ProjectListResponse>> getProjectList(@AuthenticationPrincipal CustomOAuth2User user) {
        return ResponseEntity.ok(ApiResponse.success(projectFacade.getProjectList(user.getUserId())));
    }

    @PostMapping()
    public ResponseEntity<ApiResponse<ProjectCreateResponse>> createProject(
            @RequestBody @Valid ProjectCreateRequest projectCreateRequest,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        Integer userId = user.getUserId();
        return ResponseEntity.ok(ApiResponse.success(projectFacade.createProject(projectCreateRequest, userId)));
    }

    @PostMapping("/{projectId}/snapshot")
    public ResponseEntity<ApiResponse<ProjectSnapshotSaveResponse>> saveProjectSnapshot(
            @PathVariable Integer projectId,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(projectFacade.saveProjectSnapshot(projectId, user.getUserId())));
    }
}
