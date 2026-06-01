package com.salmon.studion.domain.track.entity;

import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.global.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "master_track")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class MasterTrack extends BaseEntity {

    @Id
    @Column(name = "project_id")
    private Integer id;

    @MapsId
    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "project_id")
    private Project project;

    @Column(name = "is_soloed", nullable = false)
    private Boolean isSoloed = false;

    @Column(name = "is_muted", nullable = false)
    private Boolean isMuted = false;

    @Column(name = "volume", nullable = false)
    private Double volume = 0.0;

    @Column(name = "pan", nullable = false)
    private Integer pan = 0;

    public static MasterTrack create(
            Project project
    ) {
        MasterTrack masterTrack = new MasterTrack();
        masterTrack.project = project;
        masterTrack.isSoloed = false;
        masterTrack.isMuted = false;
        masterTrack.volume = 0.0;
        masterTrack.pan = 0;
        return masterTrack;
    }

}
