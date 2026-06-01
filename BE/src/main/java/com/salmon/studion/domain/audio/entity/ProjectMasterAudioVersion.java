package com.salmon.studion.domain.audio.entity;

import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.global.common.entity.BaseEntity;
import com.salmon.studion.global.common.enums.AudioVersionStatus;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "project_master_audio_version")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ProjectMasterAudioVersion extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "project_id", nullable = false)
    private Project project;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "audio_metadata_id")
    private AudioMetadata audioMetadata;

    @Column(name = "name", nullable = false, length = 50)
    private String name;

    @Column(name = "memo")
    private String memo;

    @Enumerated(EnumType.STRING)
    @Column(name = "status")
    private AudioVersionStatus status;

    @Column(name = "failed_reason", length = 1000)
    private String failedReason;

    @Lob
    @Column(name = "render_snapshot_json", columnDefinition = "LONGTEXT")
    private String renderSnapshotJson;

    public static ProjectMasterAudioVersion createProcessing(
            Project project,
            String name,
            String memo,
            String renderSnapshotJson
    ) {
        ProjectMasterAudioVersion audioVersion = new ProjectMasterAudioVersion();
        audioVersion.project = project;
        audioVersion.name = name;
        audioVersion.memo = memo;
        audioVersion.status = AudioVersionStatus.PROCESSING;
        audioVersion.renderSnapshotJson = renderSnapshotJson;
        return audioVersion;
    }

    public static ProjectMasterAudioVersion createReady(
            Project project,
            String name,
            String memo,
            AudioMetadata audioMetadata
    ) {
        ProjectMasterAudioVersion audioVersion = new ProjectMasterAudioVersion();
        audioVersion.project = project;
        audioVersion.name = name;
        audioVersion.memo = memo;
        audioVersion.audioMetadata = audioMetadata;
        audioVersion.status = AudioVersionStatus.READY;
        audioVersion.failedReason = null;
        audioVersion.renderSnapshotJson = null;
        return audioVersion;
    }

    public void markReady(AudioMetadata audioMetadata) {
        this.audioMetadata = audioMetadata;
        this.status = AudioVersionStatus.READY;
        this.failedReason = null;
    }

    public void markFailed(String failedReason) {
        this.status = AudioVersionStatus.FAILED;
        this.failedReason = failedReason;
    }

}
