package com.salmon.studion.domain.audio.render;

import com.salmon.studion.domain.audio.entity.AudioMetadata;
import com.salmon.studion.domain.audio.repository.AudioMetadataRepository;
import com.salmon.studion.domain.audio.render.dto.AudioVersionRenderResult;
import com.salmon.studion.global.infrastructure.s3.S3StorageService;
import com.salmon.studion.global.infrastructure.s3.dto.UploadedObjectResult;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.File;

@Service
@RequiredArgsConstructor
public class AudioVersionRenderStorageService {

    private final S3StorageService s3StorageService;
    private final AudioMetadataRepository audioMetadataRepository;

    @Transactional
    public AudioMetadata storeRenderedAudio(Integer projectId, AudioVersionRenderResult renderResult) {
        File outputFile = renderResult.getOutputPath().toFile();
        UploadedObjectResult uploadedObject = s3StorageService.uploadMasterAudioFile(
                projectId,
                outputFile,
                renderResult.getOriginalName(),
                renderResult.getMimeType().getValue()
        );

        AudioMetadata audioMetadata = AudioMetadata.create(
                uploadedObject.getObjectKey(),
                renderResult.getOriginalName(),
                uploadedObject.getStoredName(),
                renderResult.getMimeType(),
                uploadedObject.getSizeBytes().intValue(),
                renderResult.getDurationMs()
        );

        return audioMetadataRepository.save(audioMetadata);
    }
}
