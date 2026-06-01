package com.salmon.studion.domain.project.controller;

import com.salmon.studion.domain.project.dto.response.ProjectInvitationAcceptResponse;
import com.salmon.studion.domain.project.dto.response.ProjectInvitationCreateResponse;
import com.salmon.studion.domain.project.facade.ProjectInviteFacade;
import com.salmon.studion.global.auth.CustomOAuth2User;
import com.salmon.studion.global.common.response.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class ProjectInviteController {

    private final ProjectInviteFacade projectInviteFacade;

    @PostMapping("/projects/{projectId}/invitations")
    public ResponseEntity<ApiResponse<ProjectInvitationCreateResponse>> createOrRefreshInvitation(
            @PathVariable Integer projectId,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(projectInviteFacade.createOrRefreshInvitation(projectId, user.getUserId())));
    }

    @PostMapping("/invitations/{inviteCode}/accept")
    public ResponseEntity<ApiResponse<ProjectInvitationAcceptResponse>> acceptInvitation(
            @PathVariable String inviteCode,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(projectInviteFacade.acceptInvitation(inviteCode, user.getUserId())));
    }
}
