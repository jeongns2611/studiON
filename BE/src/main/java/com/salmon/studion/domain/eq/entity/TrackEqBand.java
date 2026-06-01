package com.salmon.studion.domain.eq.entity;

import com.salmon.studion.global.common.entity.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "track_eq_band")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class TrackEqBand extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "track_eq_id", nullable = false)
    private TrackEq trackEq;

    @Column(name = "band_order", nullable = false)
    private Integer bandOrder;

    @Column(name = "eq_type_code", nullable = false)
    private Integer eqTypeCode;

    @Column(name = "frequency_hz", nullable = false)
    private Integer frequencyHz;

    @Column(name = "q", nullable = false)
    private Double q;

    @Column(name = "gain_delta_db", nullable = false)
    private Double gainDeltaDb;

    @Column(name = "job_id")
    private Integer jobId;

    @Column(name = "suggestion_action_id")
    private Integer suggestionActionId;

    @Column(name = "applied_suggestion_id")
    private Integer appliedSuggestionId;

    @Column(name = "source_type_code", nullable = false)
    private Integer sourceTypeCode;

    public static TrackEqBand create(
            TrackEq trackEq,
            Integer bandOrder,
            Integer eqTypeCode,
            Integer frequencyHz,
            Double q,
            Double gainDeltaDb,
            Integer jobId,
            Integer suggestionActionId,
            Integer appliedSuggestionId,
            Integer sourceTypeCode
    ) {
        TrackEqBand band = new TrackEqBand();
        band.trackEq = trackEq;
        band.bandOrder = bandOrder;
        band.eqTypeCode = eqTypeCode;
        band.frequencyHz = frequencyHz;
        band.q = q;
        band.gainDeltaDb = gainDeltaDb;
        band.jobId = jobId;
        band.suggestionActionId = suggestionActionId;
        band.appliedSuggestionId = appliedSuggestionId;
        band.sourceTypeCode = sourceTypeCode;
        return band;
    }
}
