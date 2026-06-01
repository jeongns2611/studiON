package com.salmon.studion.domain.audio.entity;

import com.salmon.studion.global.common.entity.BaseEntity;
import com.salmon.studion.global.common.enums.MimeType;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.SQLRestriction;

import java.time.Instant;

@Getter
@Entity
@Table(name = "audio_metadata")
@SQLDelete(sql = "update audio_metadata set deleted_at = now() where id = ?")
@SQLRestriction("deleted_at is null")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class AudioMetadata extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "object_key", nullable = false, length = 1024)
    private String objectKey;

    @Column(name = "original_name", nullable = false)
    private String originalName;

    @Column(name = "stored_name", nullable = false)
    private String storedName;

    @Enumerated(EnumType.STRING)
    @Column(name = "mime_type")
    private MimeType mimeType;

    @Column(name = "size_bytes", nullable = false)
    private Integer sizeBytes;

    @Column(name = "duration_ms", nullable = false)
    private Integer durationMs;

    @Column(name = "deleted_at")
    private Instant deletedAt;

    public static AudioMetadata create(
            String objectKey,
            String originalName,
            String storedName,
            MimeType mimeType,
            Integer sizeBytes,
            Integer durationMs
    ) {
        AudioMetadata audioMetadata = new AudioMetadata();
        audioMetadata.objectKey = objectKey;
        audioMetadata.originalName = originalName;
        audioMetadata.storedName = storedName;
        audioMetadata.mimeType = mimeType;
        audioMetadata.sizeBytes = sizeBytes;
        audioMetadata.durationMs = durationMs;
        return audioMetadata;
    }
}
