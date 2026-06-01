package com.salmon.studion.domain.comment.controller;

import com.salmon.studion.domain.comment.dto.response.CommentsGetResponse;
import com.salmon.studion.domain.comment.facade.CommentFacade;
import com.salmon.studion.global.auth.CustomOAuth2User;
import com.salmon.studion.global.common.response.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/projects/{projectId}/comments")
@RequiredArgsConstructor
public class CommentController {

    private final CommentFacade commentFacade;

    @GetMapping()
    ResponseEntity<ApiResponse<CommentsGetResponse>> getComments(
            @PathVariable Integer projectId,
            @RequestParam(required = false) Boolean isResolved,
            @RequestParam(required = false) Integer trackId,
            @RequestParam(defaultValue = "false") boolean mentionedMe,
            @AuthenticationPrincipal CustomOAuth2User user
            ) {
        return ResponseEntity.ok(ApiResponse.success(commentFacade.getComments(projectId, isResolved, trackId, mentionedMe, user.getUserId())));
    }

}
