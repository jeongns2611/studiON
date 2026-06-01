package com.salmon.studion.domain.auth.entity;

import com.salmon.studion.global.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Table(name = "position_detail")
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class PositionDetail extends BaseEntity {

    @Id
    private Integer code;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "group_code")
    private PositionGroup positionGroup;

    @Column(nullable = false, length = 50)
    private String name;

    @Column(name = "`order`", nullable = false)
    private Integer order;
}
