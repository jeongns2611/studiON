package com.salmon.studion.domain.audio.controller;

import com.salmon.studion.domain.audio.dto.request.AudioUploadUrlRequest;
import com.salmon.studion.domain.audio.dto.request.AudioVersionCreateRequest;
import com.salmon.studion.domain.audio.dto.request.AudioVersionUploadedCreateRequest;
import com.salmon.studion.domain.audio.dto.response.AudioVersionCreateResponse;
import com.salmon.studion.domain.audio.dto.response.AudioVersionDeleteResponse;
import com.salmon.studion.domain.audio.dto.response.AudioVersionDownloadUrlResponse;
import com.salmon.studion.domain.audio.dto.response.AudioVersionListResponse;
import com.salmon.studion.domain.audio.dto.response.AudioVersionUploadUrlResponse;
import com.salmon.studion.domain.audio.facade.AudioVersionFacade;
import com.salmon.studion.global.auth.CustomOAuth2User;
import com.salmon.studion.global.common.response.ApiResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/projects/{projectId}/versions")
@RequiredArgsConstructor
public class AudioVersionController {

    private final AudioVersionFacade audioVersionFacade;

    /**
     * 프로젝트의 오디오 버전 저장 요청 API (오디오 생성 자체는 비동기 처리)
     */
    @PostMapping()
    public ResponseEntity<ApiResponse<AudioVersionCreateResponse>> createAudioVersion(
            @PathVariable Integer projectId,
            @Valid @RequestBody AudioVersionCreateRequest request,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(ApiResponse.success(audioVersionFacade.createAudioVersion(projectId, request, user.getUserId())));
    }

    @PostMapping("/upload-url")
    public ResponseEntity<ApiResponse<AudioVersionUploadUrlResponse>> getAudioVersionUploadUrl(
            @PathVariable Integer projectId,
            @Valid @RequestBody AudioUploadUrlRequest request,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(audioVersionFacade.getAudioVersionUploadUrl(projectId, request, user.getUserId())));
    }

    @PostMapping("/uploaded")
    public ResponseEntity<ApiResponse<AudioVersionCreateResponse>> createUploadedAudioVersion(
            @PathVariable Integer projectId,
            @Valid @RequestBody AudioVersionUploadedCreateRequest request,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(audioVersionFacade.createUploadedAudioVersion(projectId, request, user.getUserId())));
    }

    @GetMapping()
    public ResponseEntity<ApiResponse<AudioVersionListResponse>> getAudioVersionList(
            @PathVariable Integer projectId,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(audioVersionFacade.getAudioVersionList(projectId, user.getUserId())));
    }

    @GetMapping("/{versionId}/download-url")
    public ResponseEntity<ApiResponse<AudioVersionDownloadUrlResponse>> getAudioVersionDownloadUrl(
            @PathVariable Integer projectId,
            @PathVariable Integer versionId,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(audioVersionFacade.getAudioVersionDownloadUrl(projectId, versionId, user.getUserId())));
    }

    @DeleteMapping("/{versionId}")
    public ResponseEntity<ApiResponse<AudioVersionDeleteResponse>> deleteAudioVersion(
            @PathVariable Integer projectId,
            @PathVariable Integer versionId,
            @AuthenticationPrincipal CustomOAuth2User user
    ) {
        return ResponseEntity.ok(ApiResponse.success(audioVersionFacade.deleteAudioVersion(projectId, versionId, user.getUserId())));
    }
}
