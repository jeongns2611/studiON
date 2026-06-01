package com.salmon.studion.domain.clip.entity;

import com.salmon.studion.domain.audio.entity.AudioMetadata;
import com.salmon.studion.domain.track.entity.Track;
import com.salmon.studion.global.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "clip")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Clip extends BaseEntity {

    @Id
    private Integer id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "track_id", nullable = false)
    private Track track;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "audio_metadata_id", nullable = false)
    private AudioMetadata audioMetadata;

    @Column(name = "color", nullable = false, length = 7)
    private String color = "#FFFFFF";

    @Column(name = "start", nullable = false)
    private Double start = 1.0;

    @Column(name = "duration", nullable = false)
    private Double duration = 1.0;

    @Column(name = "audio_start_ms", nullable = false)
    private Integer audioStartMs = 0;

    @Column(name = "audio_duration_ms", nullable = false)
    private Integer audioDurationMs = 0;

    public static Clip create(Integer id, Track track, AudioMetadata audioMetadata, String color,
                               Double start, Double duration, Integer audioStartMs, Integer audioDurationMs) {
        Clip clip = new Clip();
        clip.id = id;
        clip.track = track;
        clip.audioMetadata = audioMetadata;
        clip.color = color != null ? color : "#FFFFFF";
        clip.start = start != null ? start : 1.0;
        clip.duration = duration != null ? duration : 1.0;
        clip.audioStartMs = audioStartMs != null ? audioStartMs : 0;
        clip.audioDurationMs = audioDurationMs != null ? audioDurationMs : 0;
        return clip;
    }

    public void update(Track track, Double start, Double duration, Integer audioStartMs, Integer audioDurationMs) {
        this.track = track;
        this.start = start;
        this.duration = duration;
        this.audioStartMs = audioStartMs;
        this.audioDurationMs = audioDurationMs;
    }
}
