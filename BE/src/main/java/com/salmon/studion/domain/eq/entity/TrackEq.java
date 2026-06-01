package com.salmon.studion.domain.eq.entity;

import com.salmon.studion.global.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "track_eq")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class TrackEq extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "track_id", nullable = false)
    private Integer trackId;

    @Column(name = "project_id", nullable = false)
    Integer projectId;

    public static TrackEq create(
            Integer trackId,
            Integer projectId
    ) {
        TrackEq trackEq = new TrackEq();

        trackEq.trackId = trackId;
        trackEq.projectId = projectId;

        return trackEq;
    }

}
