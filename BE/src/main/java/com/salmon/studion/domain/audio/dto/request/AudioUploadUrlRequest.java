package com.salmon.studion.domain.audio.dto.request;

import com.salmon.studion.global.common.enums.MimeType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class AudioUploadUrlRequest {

    @NotBlank(message = "원본 파일명은 필수입니다.")
    private String originalName;

    @NotNull(message = "오디오 MIME 타입은 필수입니다.")
    private MimeType mimeType;

    @NotNull(message = "오디오 파일 크기는 필수입니다.")
    @Positive(message = "오디오 파일 크기는 0보다 커야 합니다.")
    private Integer sizeBytes;
}
