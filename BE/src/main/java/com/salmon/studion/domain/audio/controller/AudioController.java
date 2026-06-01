package com.salmon.studion.domain.audio.controller;

import com.salmon.studion.domain.audio.dto.request.AudioListRequest;
import com.salmon.studion.domain.audio.dto.request.AudioMetadataCreateRequest;
import com.salmon.studion.domain.audio.dto.request.AudioUploadUrlRequest;
import com.salmon.studion.domain.audio.dto.response.AudioDetailResponse;
import com.salmon.studion.domain.audio.dto.response.AudioMetadataCreateResponse;
import com.salmon.studion.domain.audio.dto.response.AudioUploadUrlResponse;
import com.salmon.studion.domain.audio.facade.AudioFacade;
import com.salmon.studion.domain.audio.dto.response.AudioListResponse;
import com.salmon.studion.global.auth.CustomOAuth2User;
import com.salmon.studion.global.common.response.ApiResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.HttpStatus;

@RestController
@RequestMapping("/api/v1/projects/{projectId}/audios")
@RequiredArgsConstructor
public class AudioController {

    private final AudioFacade audioFacade;

    @PostMapping("/upload-url")
    public ResponseEntity<ApiResponse<AudioUploadUrlResponse>> getAudioUploadUrl(
            @PathVariable Integer projectId,
            @Valid @RequestBody AudioUploadUrlRequest audioUploadUrlRequest,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(audioFacade.getAudioUploadUrl(projectId, audioUploadUrlRequest, user.getUserId())));
    }

    @PostMapping()
    public ResponseEntity<ApiResponse<AudioMetadataCreateResponse>> createAudioMetadata(
            @PathVariable Integer projectId,
            @Valid @RequestBody AudioMetadataCreateRequest audioMetadataCreateRequest,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(audioFacade.createAudioMetadata(projectId, audioMetadataCreateRequest, user.getUserId())));
    }

    @GetMapping("/{audioMetadataId}")
    public ResponseEntity<ApiResponse<AudioDetailResponse>> getAudioMetadata(
            @PathVariable Integer projectId,
            @PathVariable Integer audioMetadataId,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(audioFacade.getAudioDetail(projectId, audioMetadataId, user.getUserId())));
    }

    @PostMapping("/batch")
    public ResponseEntity<ApiResponse<AudioListResponse>> getAudiosForClips(
            @PathVariable Integer projectId,
            @Valid @RequestBody AudioListRequest audioListRequest,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(audioFacade.getAudiosForClips(projectId, audioListRequest, user.getUserId())));
    }
}
