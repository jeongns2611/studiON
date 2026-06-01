package com.salmon.studion.global.infrastructure.s3;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import com.salmon.studion.global.infrastructure.s3.dto.DownloadPresignedUrlResult;
import com.salmon.studion.global.infrastructure.s3.dto.PresignedUrlResult;
import com.salmon.studion.global.infrastructure.s3.dto.UploadedObjectResult;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.*;
import software.amazon.awssdk.services.s3.presigner.model.GetObjectPresignRequest;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.PutObjectPresignRequest;

import java.io.File;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;


@Service
@RequiredArgsConstructor
public class S3StorageService {

    private final S3Presigner s3Presigner;
    private final S3Client s3Client;
    private final S3ObjectKeyGenerator s3ObjectKeyGenerator;
    private final Clock clock;

    @Value("${cloud.aws.s3.bucket}")
    private String bucket;

    @Value("${cloud.aws.s3.upload-url-expiration-minutes}")
    private Long uploadUrlExpirationMinutes;

    public PresignedUrlResult createUploadUrl(Integer projectId, String originalName, String contentType, Integer sizeBytes) {
        String storedName = s3ObjectKeyGenerator.createStoredName(originalName);
        String objectKey = s3ObjectKeyGenerator.createAudioObjectKey(projectId, storedName);

        PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                .bucket(bucket)
                .key(objectKey)
                .contentType(contentType)
                .contentLength(sizeBytes.longValue())
                .build();

        PutObjectPresignRequest presignRequest = PutObjectPresignRequest.builder()
                .signatureDuration(Duration.ofMinutes(uploadUrlExpirationMinutes))
                .putObjectRequest(putObjectRequest)
                .build();

        String uploadUrl = s3Presigner.presignPutObject(presignRequest)
                .url()
                .toString();

        return PresignedUrlResult.of(objectKey, storedName, uploadUrl);
    }

    public UploadedObjectResult uploadMasterAudioFile(
            Integer projectId,
            File file,
            String originalName,
            String contentType
    ) {
        String storedName = s3ObjectKeyGenerator.createStoredName(originalName);
        String objectKey = s3ObjectKeyGenerator.createMasterAudioObjectKey(projectId, storedName);

        PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                .bucket(bucket)
                .key(objectKey)
                .contentType(contentType)
                .contentLength(file.length())
                .build();

        try {
            s3Client.putObject(putObjectRequest, file.toPath());
        } catch (S3Exception exception) {
            throw new BusinessException(ErrorCode.AUDIO_UPLOAD_FAILED);
        }

        return UploadedObjectResult.of(objectKey, storedName, file.length());
    }

    public DownloadPresignedUrlResult createDownloadUrl(String objectKey, String downloadFileName) {
        Duration expiration = Duration.ofMinutes(uploadUrlExpirationMinutes);
        java.time.Instant expiresAt = clock.instant().plus(expiration);

        GetObjectRequest.Builder getObjectRequestBuilder = GetObjectRequest.builder()
                .bucket(bucket)
                .key(objectKey);

        if (downloadFileName != null && !downloadFileName.isBlank()) {
            getObjectRequestBuilder.responseContentDisposition(buildDownloadContentDisposition(downloadFileName));
        }

        GetObjectPresignRequest presignRequest = GetObjectPresignRequest.builder()
                .signatureDuration(expiration)
                .getObjectRequest(getObjectRequestBuilder.build())
                .build();

        String downloadUrl = s3Presigner.presignGetObject(presignRequest)
                .url()
                .toString();

        return DownloadPresignedUrlResult.of(downloadUrl, expiresAt);
    }

    // 한글 파일명도 S3 presigned download URL에서 안전하게 처리되도록 Content-Disposition 값을 생성하는 메서드
    private String buildDownloadContentDisposition(String downloadFileName) {
        String encodedFileName = URLEncoder.encode(downloadFileName, StandardCharsets.UTF_8)
                .replace("+", "%20");

        return "attachment; filename=\"audio-version\"; filename*=UTF-8''" + encodedFileName;
    }

    public void validateUploadedObject(String objectKey, Integer expectedSizeBytes, String expectedContentType) {
        HeadObjectResponse headObjectResponse = getHeadObject(objectKey);

        validateContentLength(headObjectResponse, expectedSizeBytes);
        validateContentType(headObjectResponse, expectedContentType);
    }

    // S3에 해당 objectKey 파일이 존재하는지 확인 및 메타데이터 조회 메서드
    private HeadObjectResponse getHeadObject(String objectKey) {
        try {
            HeadObjectRequest headObjectRequest = HeadObjectRequest.builder()
                    .bucket(bucket)
                    .key(objectKey)
                    .build();

            return s3Client.headObject(headObjectRequest);
        } catch (NoSuchKeyException e) {
            throw new BusinessException(ErrorCode.AUDIO_FILE_NOT_FOUND);
        } catch (S3Exception e) {
            if (e.statusCode() == 404) {
                throw new BusinessException(ErrorCode.AUDIO_FILE_NOT_FOUND);
            }

            throw new BusinessException(ErrorCode.S3_OBJECT_VALIDATE_FAILED);
        }
    }

    private void validateContentLength(HeadObjectResponse headObjectResponse, Integer expectedSizeBytes) {
        long actualSizeBytes = headObjectResponse.contentLength();

        if (actualSizeBytes != expectedSizeBytes.longValue()) {
            throw new BusinessException(ErrorCode.AUDIO_FILE_SIZE_MISMATCH);
        }
    }

    private void validateContentType(HeadObjectResponse headObjectResponse, String expectedContentType) {
        String actualContentType = headObjectResponse.contentType();

        if (actualContentType == null || !actualContentType.equals(expectedContentType)) {
            throw new BusinessException(ErrorCode.AUDIO_CONTENT_TYPE_MISMATCH);
        }
    }
}
