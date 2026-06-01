package com.salmon.studion.domain.project.entity;

import com.salmon.studion.global.common.entity.BaseEntity;
import com.salmon.studion.global.common.enums.ProjectMode;
import com.salmon.studion.global.common.enums.RootNote;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.SQLRestriction;

import java.time.Instant;

@Getter
@Entity
@Table(name = "project")
@SQLDelete(sql = "update project set deleted_at = now() where id = ?")
@SQLRestriction("deleted_at is null")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Project extends BaseEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "name", nullable = false, length = 100)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(name = "root_note", nullable = false, length = 10)
    private RootNote rootNote = RootNote.C;

    @Enumerated(EnumType.STRING)
    @Column(name = "mode", nullable = false, length = 10)
    private ProjectMode mode = ProjectMode.MAJOR;

    @Column(name = "tempo", nullable = false)
    private Double tempo = 120.00;

    @Column(name = "time_sig_numerator", nullable = false)
    private Integer timeSigNumerator = 4;

    @Column(name = "time_sig_denominator", nullable = false)
    private Integer timeSigDenominator = 4;

    @Column(name = "total_bar_count", nullable = false)
    private Integer totalBarCount = 0;

    @Column(name = "total_play_time_ms", nullable = false)
    private Integer totalPlayTimeMs = 0;

    @Column(name = "track_count", nullable = false)
    private Integer trackCount = 0;

    @Column(name = "total_audio_size_byte", nullable = false)
    private Long totalAudioSizeByte = 0L;

    @Column(name = "deleted_at")
    private Instant deletedAt;

    @Column(name = "last_update_at")
    private Instant lastUpdateAt;

    public static Project create(
            String name,
            RootNote rootNote,
            ProjectMode mode,
            Double tempo,
            Integer timeSigNumerator,
            Integer timeSigDenominator,
            Instant lastUpdateAt
    ) {
        Project project = new Project();
        project.name = name;
        project.rootNote = rootNote;
        project.mode = mode;
        project.tempo = tempo;
        project.timeSigNumerator = timeSigNumerator;
        project.timeSigDenominator = timeSigDenominator;
        project.totalBarCount = 0;
        project.totalPlayTimeMs = 0;
        project.trackCount = 0;
        project.totalAudioSizeByte = 0L;
        project.lastUpdateAt = lastUpdateAt;
        return project;
    }

    public void rename(String name, Instant lastUpdateAt) {
        this.name = name;
        this.lastUpdateAt = lastUpdateAt;
    }

    public void changeTempo(Double tempo, Instant lastUpdateAt) {
        this.tempo = tempo;
        this.lastUpdateAt = lastUpdateAt;
    }

    public void changeKey(RootNote rootNote, ProjectMode mode, Instant lastUpdateAt) {
        this.rootNote = rootNote;
        this.mode = mode;
        this.lastUpdateAt = lastUpdateAt;
    }

    public void changeTimeSignature(Integer timeSigNumerator, Integer timeSigDenominator, Instant lastUpdateAt) {
        this.timeSigNumerator = timeSigNumerator;
        this.timeSigDenominator = timeSigDenominator;
        this.lastUpdateAt = lastUpdateAt;
    }

    public void refreshSnapshotStatistics(
            Integer trackCount,
            Integer totalBarCount,
            Integer totalPlayTimeMs,
            Long totalAudioSizeByte,
            Instant lastUpdateAt
    ) {
        this.trackCount = trackCount;
        this.totalBarCount = totalBarCount;
        this.totalPlayTimeMs = totalPlayTimeMs;
        this.totalAudioSizeByte = totalAudioSizeByte;
        this.lastUpdateAt = lastUpdateAt;
    }

}
