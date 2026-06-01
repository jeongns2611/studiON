package com.salmon.studion.domain.track.repository;

import com.salmon.studion.domain.track.entity.TrackBaseEventDocument;
import org.springframework.data.mongodb.repository.MongoRepository;

public interface TrackEventRepository extends MongoRepository<TrackBaseEventDocument, String> {
}
